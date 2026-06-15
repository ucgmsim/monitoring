import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typer
from matplotlib import pyplot as plt

from monitoring import burndown

app = typer.Typer()


@dataclass
class TimestepLog:
    timestep: int
    cpu: float
    mpi: float
    mbyte: float
    mpi_percent: float
    time: float
    percent: float
    cumulative: int
    cumulative_percent: float


@dataclass
class RLog:
    timesteps: list[TimestepLog]
    nt: int


_SENTINEL = "time step       CPU  MPI_only    Mbyte  %Real        CPU  %Real            CPU  %Real"
_LF_LOG_RE = re.compile(
    r"""
   \s*
   (?P<timestep>\d+)
   \s*
   (?P<cpu>\d+\.\d+)
   \s*
   (?P<mpi>\d+\.\d+)
   \s*
   (?P<mbyte>\d+\.\d+)
   \s*
   (?P<mpi_percent>\d+\.\d+)
   \s*
   (?P<time>\d+\.\d+)
   \s*
   (?P<percent>\d+\.\d+)
   \s*
   (?P<cumulative>\d+)\.
   \s*
   (?P<cumulative_percent>\d+.\d+)
""",
    re.VERBOSE,
)
_LF_NT_RE = re.compile(r"nt= (\d+)")


def parse_lf_log(log_file: Path) -> RLog:
    timesteps = []
    nt = None
    with open(log_file, "r") as f:
        for line in f:
            if match := re.search(_LF_NT_RE, line):
                nt = int(match.group(1))
            elif line.strip() == _SENTINEL:
                break
        for line in f:
            if match := re.match(_LF_LOG_RE, line):
                timesteps.append(
                    TimestepLog(
                        timestep=int(match.group("timestep")),
                        cpu=float(match.group("cpu")),
                        mpi=float(match.group("mpi")),
                        mbyte=float(match.group("mbyte")),
                        mpi_percent=float(match.group("mpi_percent")),
                        time=float(match.group("time")),
                        percent=float(match.group("percent")),
                        cumulative=int(match.group("cumulative")),
                        cumulative_percent=float(match.group("cumulative_percent")),
                    )
                )
    if not nt:
        raise ValueError("Could not parse number of timesteps from RLog file.")
    return RLog(timesteps=timesteps, nt=nt)


@app.command("burndown", help="Show a burndown of an LF job.")
def lf_burndown(
    rlog_path: Annotated[Path, typer.Argument(help="Path to rlog file to analyse.")],
    start_time: Annotated[datetime, typer.Argument(help="Start time for job.")],
    running_time: Annotated[float, typer.Argument(help="Total planned time for the job (hours).")],
    output: Annotated[Path, typer.Argument(help="Output path for burndown chart.")],
    timezone: Annotated[
        str | None,
        typer.Option(
            "--tz",
            help="IANA time zone name for start time (if none, start time has no timezone information). If provided, times will be converted to local time.",
        ),
    ] = None,
    title: Annotated[str | None, typer.Option(help="Set plot title.")] = None,
) -> None:
    rlog = parse_lf_log(rlog_path)
    if timezone:
        try:
            start_time = start_time.replace(tzinfo=ZoneInfo(timezone))
        except ZoneInfoNotFoundError:
            print(f"Invalid time zone: '{timezone}'.")
        local_timezone = datetime.now().astimezone().tzinfo
        start_time = start_time.astimezone(local_timezone)
    timestamps = [start_time + timedelta(seconds=timestep.cumulative) for timestep in rlog.timesteps[1:]]
    iterations = [100] * (len(rlog.timesteps) - 1)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    end_time = start_time + timedelta(hours=running_time)
    burndown.burndown(
        ax,
        timestamps,
        rlog.nt,
        tasks_completed=iterations,
        start_time=start_time,
        deadline=end_time,
        task_units="time-step",
    )
    if title:
        plt.title(title)
    fig.tight_layout()
    fig.savefig(output)


if __name__ == "__main__":
    app()

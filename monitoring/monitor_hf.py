"""Plot high-frequency burndown charts."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import IO, Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typer
from matplotlib import pyplot as plt

from monitoring import burndown

app = typer.Typer()


@dataclass
class HFLog:
    """A dataclass representing the contents of a high-frequency log file."""

    timestamps: list[datetime]
    """The timestamps of completed jobs"""
    stations: int
    """The station count."""


_HF_COMPLETED_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3} - .* - INFO - Finished .* for station: .*")
_HF_STATION_COUNT = re.compile(r"Successfully read (\d+) stations")


def parse_hf_timestamp(line: str) -> datetime | None:
    """Parse an HF timestamp line.



    Parameters
    ----------
    line : str
        The line to parse, should have format YYYY-MM-DD HH:MM:SS,XX -
        .* - INFO - Finished .* for station: .*


    Returns
    -------
    datetime | None
        A parsed timestamp for station completion, or None if the line
        does not match the expected format.
    """
    if match := re.match(_HF_COMPLETED_RE, line):
        ts_str = match.group(1)
        time = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return time


def parse_hf_station_count(line: str) -> int | None:
    """Parse an HF station count line.

    Parameters
    ----------
    line : str
        The line to parse, should have format Sucessfully read DDDDD stations.

    Returns
    -------
    int | None
        A parsed number of stations, or None if the line does not match the expected format.
    """
    if match := re.search(_HF_STATION_COUNT, line):
        stations = int(match.group(1))
        return stations


def parse_hf_log(log_file: IO[str]) -> HFLog:
    """Parse a high-frequency event log file.

    Parameters
    ----------
    log_file : IO[str]
        HF log file handle to parse.

    Returns
    -------
    HFLog
        The parsed high-frequency log file.

    Raises
    ------
    ValueError
        If the log file could identify the number of stations.
    """
    timestamps = []
    stations = None
    for line in log_file:
        stations = stations or parse_hf_station_count(line)
        if timestamp := parse_hf_timestamp(line):
            timestamps.append(timestamp)

    if not stations:
        raise ValueError("Could not parse number of stations from log file.")
    return HFLog(timestamps=timestamps, stations=stations)


@app.command("burndown", help="Show a burndown of an HF job.")
def hf_burndown(
    hflog_path: Annotated[Path, typer.Argument(help="Path to HF Log file to analyse.")],
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
    """Plot a burndown chart of a high-frequency job.

    Parameters
    ----------
    hflog_path : Path
        HF frequency log path.
    start_time : datetime
        Start time of the job.
    running_time : float
        Time (in hours) for the job.
    output : Path
        Chart output directory.
    timezone : str | None
        Timezone for the start time (and times in the log file). If
        provided, times are translated to local time.
    title : str | None
        Title for the plot.
    """

    with open(hflog_path, "r") as f:
        hf_log = parse_hf_log(f)
    timestamps = hf_log.timestamps
    if timezone:
        try:
            time_zone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            print(f"Invalid time zone: '{timezone}'.")
            return
        start_time = start_time.replace(tzinfo=time_zone)
        local_timezone = datetime.now().astimezone().tzinfo
        start_time = start_time.astimezone(local_timezone)
        timestamps = [timestamp.replace(tzinfo=time_zone).astimezone(local_timezone) for timestamp in timestamps]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    end_time = start_time + timedelta(hours=running_time)
    burndown.burndown(
        ax,
        timestamps,
        hf_log.stations,
        start_time=start_time,
        deadline=end_time,
        task_units="station",
    )
    if title:
        plt.title(title)
    fig.tight_layout()
    fig.savefig(output)


if __name__ == "__main__":
    app()

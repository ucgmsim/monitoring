"""Plot high-frequency burndown charts.

Example
-------
Run the HF monitor against a JSON log and the planned station file:

    uv run python -m monitoring.monitor_hf \
        /path/to/hf-job-log.jsonl \
        /path/to/planned-stations.ll \
        "DateTime of run start, e.g. YYYY-MM-DD:HH:MM:SS" \
        "planned run time in hours, e.g. 96 for 4 days" \
        /path/to/hf-burndown.png

Specific example
----------------
Command used for the Clarence HF monitoring run:

    uv run python -m monitoring.monitor_hf \
        /home/arr65/data/hf_monitoring/job.out \
        /home/arr65/data/hf_monitoring/stations_input.ll \
        2026-06-15T00:58:10 \
        96 \
        /home/arr65/data/hf_monitoring/job.out.png
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from json import JSONDecodeError
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
    """The timestamps of station progress records."""


@dataclass
class HFProgressSummary:
    """Progress metrics derived from the station file and log timestamps."""

    station_count: int
    stations_logged: int
    stations_remaining: int
    average_seconds_per_station: float | None
    estimated_seconds_remaining: float | None
    estimated_total_wall_clock_seconds: float | None
    estimated_completion_time: datetime | None


_HF_JSON_STATION_EVENT = "running hf"
_HF_TIMESTAMPS_ERROR = "Could not parse any station progress timestamps from log file."
_STATION_COUNT_ERROR = "Could not parse any station records from station file."
_STATION_LINE_ERROR = "Could not parse station file line. Expected 'lon lat station_name'."


def parse_hf_json_timestamp(value: object) -> datetime | None:
    """Parse a timestamp from a structured HF log record."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_hf_json_record(line: str) -> tuple[str, datetime] | None:
    """Parse a station progress record from a JSON log line."""
    try:
        record = json.loads(line)
    except JSONDecodeError:
        return None

    if not isinstance(record, dict):
        return None
    if record.get("event") != _HF_JSON_STATION_EVENT:
        return None
    station = record.get("station")
    timestamp = parse_hf_json_timestamp(record.get("timestamp"))
    if not isinstance(station, str) or not timestamp:
        return None
    return station, timestamp


def parse_station_count(station_file: IO[str]) -> int:
    """Count station records in a station file."""
    station_count = 0
    for line in station_file:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        columns = stripped.split()
        if len(columns) < 3:
            raise ValueError(_STATION_LINE_ERROR)
        try:
            float(columns[0])
            float(columns[1])
        except ValueError as exc:
            raise ValueError(_STATION_LINE_ERROR) from exc
        station_count += 1

    if not station_count:
        raise ValueError(_STATION_COUNT_ERROR)
    return station_count


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
        If the log file could not identify any station progress timestamps.
    """
    timestamps = []
    stations = set()
    for line in log_file:
        if json_record := parse_hf_json_record(line):
            station, timestamp = json_record
            if station not in stations:
                timestamps.append(timestamp)
            stations.add(station)

    if not timestamps:
        raise ValueError(_HF_TIMESTAMPS_ERROR)
    timestamps.sort()
    return HFLog(timestamps=timestamps)


def build_progress_summary(
    station_count: int,
    timestamps: list[datetime],
    start_time: datetime,
) -> HFProgressSummary:
    """Build progress and ETA metrics for an HF job."""
    stations_logged = len(timestamps)
    stations_remaining = max(station_count - stations_logged, 0)
    latest_timestamp = max(timestamps)
    elapsed_seconds = (latest_timestamp - start_time).total_seconds()
    if elapsed_seconds <= 0 or stations_logged == 0:
        return HFProgressSummary(
            station_count=station_count,
            stations_logged=stations_logged,
            stations_remaining=stations_remaining,
            average_seconds_per_station=None,
            estimated_seconds_remaining=None,
            estimated_total_wall_clock_seconds=None,
            estimated_completion_time=None,
        )

    average_seconds_per_station = elapsed_seconds / stations_logged
    estimated_seconds_remaining = stations_remaining * average_seconds_per_station
    estimated_total_wall_clock_seconds = station_count * average_seconds_per_station
    estimated_completion_time = latest_timestamp + timedelta(seconds=estimated_seconds_remaining)
    return HFProgressSummary(
        station_count=station_count,
        stations_logged=stations_logged,
        stations_remaining=stations_remaining,
        average_seconds_per_station=average_seconds_per_station,
        estimated_seconds_remaining=estimated_seconds_remaining,
        estimated_total_wall_clock_seconds=estimated_total_wall_clock_seconds,
        estimated_completion_time=estimated_completion_time,
    )


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a compact human-readable string."""
    total_seconds = round(seconds)
    days, remainder = divmod(total_seconds, 24 * 60 * 60)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def print_progress_summary(summary: HFProgressSummary) -> None:
    """Print progress and ETA metrics for an HF job."""
    print(f"Number of stations to do: {summary.station_count}")
    print(f"Stations logged so far: {summary.stations_logged}")
    print(f"Stations remaining: {summary.stations_remaining}")
    if summary.average_seconds_per_station is None or summary.estimated_seconds_remaining is None:
        print("Average time per station: unavailable")
        print("Estimated total wall clock time: unavailable")
        print("Estimated time until completion: unavailable")
        return

    print(f"Average time per station: {summary.average_seconds_per_station:.2f}s")
    if summary.estimated_total_wall_clock_seconds is not None:
        total_wall_clock = format_duration(summary.estimated_total_wall_clock_seconds)
        print(f"Estimated total wall clock time: {total_wall_clock}")
    print(f"Estimated time until completion: {format_duration(summary.estimated_seconds_remaining)}")
    if summary.estimated_completion_time is not None:
        completion_time = summary.estimated_completion_time.isoformat(sep=" ", timespec="seconds")
        print(f"Estimated completion time: {completion_time}")


@app.command("burndown", help="Show a burndown of an HF job.")
def hf_burndown(
    hflog_path: Annotated[Path, typer.Argument(help="Path to HF Log file to analyse.")],
    station_file: Annotated[Path, typer.Argument(help="Path to station file for the planned HF job.")],
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
    station_file : Path
        Station file path for the planned HF job.
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

    with open(hflog_path) as f:
        hf_log = parse_hf_log(f)
    with open(station_file) as f:
        station_count = parse_station_count(f)

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
        timestamps = [
            (timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=time_zone)).astimezone(local_timezone)
            for timestamp in timestamps
        ]
    else:
        timestamps = [timestamp.replace(tzinfo=None) for timestamp in timestamps]

    print_progress_summary(build_progress_summary(station_count, timestamps, start_time))

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    end_time = start_time + timedelta(hours=running_time)
    burndown.burndown(
        ax,
        timestamps,
        station_count,
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

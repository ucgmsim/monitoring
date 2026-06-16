from datetime import datetime, timedelta

from matplotlib.axes import Axes
from matplotlib.dates import DateFormatter, date2num
from pluralizer import Pluralizer


def burndown(
    ax: Axes,
    timestamps: list[datetime],
    task_count: int,
    tasks_completed: list[int] | None = None,
    task_units: str = "task",
    start_time: datetime | None = None,
    deadline: datetime | None = None,
) -> None:
    """Create a burndown chart.

    Parameters
    ----------
    ax : Axes
        The axes to plot onto.
    timestamps : list[datetime]
        Timestamp of task completion.
    task_count : int
        Total task count.
    tasks_completed : list[int] | None
        If provided, indicates the number of tasks completed per timestamp (not a running total).
    task_units : str
        Units for tasks, default 'task'.
    start_time : datetime | None
        The start time, will take the first timestamp if not provided.
    deadline : datetime | None
        The deadline date.
    """
    if tasks_completed:
        running_total = [tasks_completed[0]]
        for completed in tasks_completed[1:]:
            running_total.append(running_total[-1] + completed)
    else:
        running_total = list(range(1, len(timestamps) + 1))

    task_counts = [task_count - completed for completed in running_total]
    completed_tasks = running_total[-1]
    if start_time:
        timestamps = timestamps.copy()
        timestamps.append(start_time)
        task_counts.append(task_count)

    pluraliser = Pluralizer()
    plural = pluraliser.plural(task_units)
    start_time = start_time or timestamps[0]
    latest = max(timestamps)
    run_time = (latest - start_time).total_seconds()
    avg_rate = completed_tasks / run_time

    time_required = task_count / avg_rate
    projected_endpoint = start_time + timedelta(seconds=time_required)
    ax.plot(
        [date2num(start_time), date2num(projected_endpoint)],
        [task_count, 0],
        linestyle="--",
        label=f"Projected {plural} remaining",
    )
    if deadline:
        ax.plot(
            [date2num(start_time), date2num(deadline)],
            [task_count, 0],
            label=f"Ideal {plural} remaining",
        )
        ax.axvline(
            date2num(deadline),
            ymin=0,
            ymax=1,
            label="Deadline",
        )

    ax.plot(
        date2num(timestamps),
        task_counts,
        marker="o",
        linestyle="-",
        color="red",
        label=f"{plural} remaining",
    )

    xlim_max = projected_endpoint
    if deadline and deadline > projected_endpoint:
        xlim_max = deadline
    xlim_min_num = date2num(start_time)
    xlim_max_num = date2num(xlim_max)
    xlim_padding = max((xlim_max_num - xlim_min_num) * 0.02, 1 / (24 * 60))
    ax.set_xlim(
        xlim_min_num,
        xlim_max_num + xlim_padding,
    )
    ax.set_xlabel("Time")
    ax.tick_params("x", rotation=45)
    ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d %H:%M:%S", tz=start_time.tzinfo))
    ax.set_ylabel(f"{plural} remaining")
    ax.legend()

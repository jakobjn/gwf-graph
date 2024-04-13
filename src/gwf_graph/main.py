import click
import regex as re
from graphviz import Digraph, FORMATS
from gwf import Workflow
from gwf.core import (
    CachedFilesystem,
    Context,
    get_spec_hashes,
    Graph,
    Status,
    Target,
)
from gwf.backends import create_backend
from gwf.scheduling import get_status_map
from gwf_utilization import accounting, main


STATUS_COLORS = {
    Status.CANCELLED: "purple",
    Status.FAILED: "red",
    Status.COMPLETED: "green",
    Status.RUNNING: "blue",
    Status.SUBMITTED: "yellow",
    Status.SHOULDRUN: "black",
}


def validate_output_format(context: click.Context, param: click.Parameter, value: str):
    """
    Validates that the output format is supported by graphviz.

    Args:
        context (click.Context): The click context.
        param (click.Parameter): The click parameter.
        value (str): The output format.

    Returns:
        str: The output format if it is valid.

    Raises:
        click.BadParameter: If the output format is not valid.
    """
    if value:
        value_match = re.match(r".*\.([a-z]+)$", value)
        if value_match.group(1) in FORMATS:
            return value
    raise click.BadParameter("Output format must be one of: " + ", ".join(FORMATS))


def create_graph(
    dependents: dict[set],
    status_map: dict[Target, Status],
    output: str,
):
    """
    Creates a graph visualization of the dependency graph in the gwf workflow.

    Args:
        dependents (dict): A dictionary with dependent targets as keys and sets of dependency targets
                           as values.
        status_map (dict): A dictionary with targets as keys and statuses as values.
        output (str): The name (and path) of the output graph visualization. Must end with a
                      valid graphviz format (e.g. png, svg, etc.).
    """
    output_name = "".join(output.split(".")[:-1])
    output_format = output.split(".")[-1]
    graph = Digraph(comment="Workflow", format=output_format)

    if status_map:
        for target, status in status_map.items():
            color = STATUS_COLORS.get(status, "black")
            graph.node(str(target), shape="rectangle", style="rounded", color=color)
    else:
        graph.attr("node", shape="rectangle", style="rounded")

    for target, dependencies in dependents.items():
        for dependency in dependencies:
            graph.edge(str(target), str(dependency))

    graph.render(output_name, view=True)


# @TODO: Add target resource utilization to the graph using the gwf-utilization plugin.
@click.command()
@click.option(
    "-o",
    "--output",
    default="workflow.png",
    callback=validate_output_format,
    help="The name (and path) of the output graph visualization. Must end with a valid graphviz format (e.g. png, svg, etc.). Defaults to 'workflow.png'.",
)
@click.option(
    "--status/--no-status",
    default=False,
    help="Flag to include the status (e.g., running, completed, failed) of each target in the graph.",
)
@click.pass_obj
def graph(context: Context, output, status):
    """
    Generates a graph visualization of the dependency graph in the gwf workflow. Optionally,
    the status of the targets can be included, providing insight into the workflow's current state.

    Args:
        context (gwf.core.Context): The context object from gwf.
        output (str): The name (and path) of the output graph visualization. Must end with a
                      valid graphviz format (e.g. png, svg, etc.). Defaults to 'workflow.png'.
        status (bool): If true, the status of the targets will be included in the visualization.
                       Defaults to False.
    """
    workflow = Workflow.from_context(ctx=context)
    fs = CachedFilesystem()
    graph = Graph.from_targets(targets=workflow.targets, fs=fs)
    status_map = dict()
    if status:
        spec_hashes = get_spec_hashes(
            working_dir=context.working_dir, config=context.config
        )
        backend = create_backend(
            name=context.backend,
            working_dir=context.working_dir,
            config=context.config,
        )
        status_map = get_status_map(
            graph=graph, fs=fs, backend=backend, spec_hashes=spec_hashes
        )
    create_graph(dependents=graph.dependents, status_map=status_map, output=output)

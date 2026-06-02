from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.text import Text
from rich import box

console = Console()


def print_banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Smart Job Assistant[/bold cyan]\n"
            "[dim]LLM-powered automated job applications[/dim]",
            border_style="cyan",
            padding=(1, 4),
        )
    )


def prompt_platform() -> str:
    console.print("\n[bold]Which platforms would you like to search?[/bold]")
    console.print("  [cyan]1[/cyan] Naukri")
    console.print("  [cyan]2[/cyan] LinkedIn")
    console.print("  [cyan]3[/cyan] Both")
    choice = Prompt.ask("Enter choice", choices=["1", "2", "3", "naukri", "linkedin", "both"], default="3")
    mapping = {"1": "naukri", "2": "linkedin", "3": "both"}
    return mapping.get(choice, choice)


def prompt_job_count() -> int:
    return IntPrompt.ask("\n[bold]How many jobs would you like to apply to?[/bold]", default=10)


def prompt_confidence_threshold(default: int) -> int:
    return IntPrompt.ask(
        f"\n[bold]Minimum confidence score to apply (0-100)[/bold]",
        default=default,
    )


def prompt_location() -> str:
    return Prompt.ask("\n[bold]Preferred job location[/bold]", default="India")


def print_cv_summary(cv_data) -> None:
    console.print("\n[bold green]CV Parsed Successfully[/bold green]")
    if cv_data.name:
        console.print(f"  Name      : [cyan]{cv_data.name}[/cyan]")
    if cv_data.experience_years:
        console.print(f"  Experience: [cyan]{cv_data.experience_years} years[/cyan]")
    if cv_data.job_titles:
        console.print(f"  Searching : [cyan]{', '.join(cv_data.job_titles[:3])}[/cyan]")
    if cv_data.skills:
        skills_preview = ", ".join(cv_data.skills[:8])
        console.print(f"  Top Skills: [cyan]{skills_preview}[/cyan]")


def print_login_status(platform: str, success: bool) -> None:
    icon = "[green]✓[/green]" if success else "[red]✗[/red]"
    status = "Logged in" if success else "Login failed"
    console.print(f"  {icon} {platform.capitalize()}: {status}")


def print_search_results(platform: str, count: int) -> None:
    console.print(f"  [dim]Found[/dim] [bold]{count}[/bold] [dim]listings on {platform.capitalize()}[/dim]")


def print_job_evaluation(index: int, total: int, listing, score, threshold: int) -> None:
    score_val = score.score
    if score_val >= threshold:
        score_str = f"[bold green]{score_val}[/bold green]"
        action = "[bold green]✓ APPLYING[/bold green]"
    elif score_val >= threshold - 15:
        score_str = f"[yellow]{score_val}[/yellow]"
        action = "[dim]✗ skip[/dim]"
    else:
        score_str = f"[red]{score_val}[/red]"
        action = "[dim]✗ skip[/dim]"

    title = listing.title[:40].ljust(40)
    company = listing.company[:25].ljust(25)
    console.print(
        f"[dim][{index}/{total}][/dim] {title} [dim]@[/dim] {company}  Score: {score_str}  {action}"
    )
    if score_val >= threshold and score.rationale:
        console.print(f"         [dim italic]{score.rationale[:100]}[/dim italic]")


def print_apply_result(listing, result) -> None:
    if result.success:
        console.print(f"         [green]Applied![/green]")
    elif result.status == "skipped_external":
        console.print(f"         [yellow]Skipped (external ATS)[/yellow]")
    elif result.error:
        console.print(f"         [red]Error: {result.error[:80]}[/red]")


def print_target_reached(target: int) -> None:
    console.print(f"\n[bold green]Target of {target} applications reached![/bold green]")


def print_final_summary(records: list, log_path: str) -> None:
    applied = [r for r in records if r.status == "applied"]
    skipped = [r for r in records if r.status in ("skipped", "skipped_external")]
    errors = [r for r in records if r.status == "error"]

    console.print("\n")
    table = Table(
        title="Session Summary",
        box=box.ROUNDED,
        border_style="cyan",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Jobs Analyzed", str(len(records)))
    table.add_row("[green]Applied[/green]", f"[green]{len(applied)}[/green]")
    table.add_row("[dim]Skipped[/dim]", str(len(skipped)))
    table.add_row("[red]Errors[/red]", f"[red]{len(errors)}[/red]")

    if applied:
        avg_score = sum(r.score for r in applied) / len(applied)
        table.add_row("Avg Score (applied)", f"{avg_score:.0f}")

    console.print(table)
    console.print(f"\n[dim]Full log saved → {log_path}[/dim]")


def print_error(message: str) -> None:
    console.print(f"\n[bold red]Error:[/bold red] {message}")


def print_info(message: str) -> None:
    console.print(f"[dim]{message}[/dim]")

"""
Google Maps Contact Scraper CLI Entrypoint.
Orchestrates two-stage processing:
1. Google Maps automated extraction (Playwright)
2. Asynchronous email enrichment (httpx)
3. CSV & JSON export
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from config.settings import settings
from storage.database import DatabaseManager, EnrichmentStatus
from storage.exporter import export_to_csv, export_to_json
from core.maps_worker import MapsWorker
from core.email_enricher import EmailEnricher
from loop.evaluator import PRDEvaluator

console = Console()


async def run_pipeline(
    keywords: List[str],
    limit: int,
    headless: bool,
    proxy: Optional[str],
    skip_enrich: bool,
    resume_only: bool,
    export_csv_enabled: bool,
    export_json_enabled: bool,
):
    db = DatabaseManager()

    console.print(Panel.fit(
        "[bold cyan]Google Maps Business Contact Scraper[/bold cyan]\n"
        "[dim]Two-stage contact extraction: Google Maps + Async Website Email Enrichment[/dim]",
        border_style="cyan"
    ))

    # STAGE 1: Maps Extraction
    if not resume_only:
        maps_worker = MapsWorker(db_manager=db, headless=headless, proxy_url=proxy)
        for kw in keywords:
            console.print(f"\n[bold yellow]Stage 1: Scraping Google Maps for '[green]{kw}[/green]' (Target: {limit} results)...[/bold yellow]")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task_id = progress.add_task(f"Navigating & scrolling Maps for '{kw}'...", total=None)

                def on_maps_progress(item):
                    progress.update(task_id, description=f"Extracted: [white]{item.get('business_name')}[/white]")

                await maps_worker.search_and_extract(
                    keyword=kw,
                    limit=limit,
                    on_progress=on_maps_progress
                )
    else:
        console.print("[yellow]Skipping Stage 1 (--resume flag active), proceeding directly to Stage 2 Enrichment.[/yellow]")

    # STAGE 2: Email Enrichment
    if not skip_enrich:
        enricher = EmailEnricher(db_manager=db)
        pending = db.get_pending_enrichment_entities()

        if pending:
            console.print(f"\n[bold yellow]Stage 2: Enriching {len(pending)} pending websites for business emails...[/bold yellow]")
            with Progress(
                SpinnerColumn(),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("{task.description}"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                enrich_task = progress.add_task("Crawling business websites...", total=len(pending))

                def on_enrich_progress(entity, emails, status):
                    msg = f"[green]{entity.business_name}[/green]: {len(emails)} emails ({status.value})"
                    progress.update(enrich_task, advance=1, description=msg)

                await enricher.enrich_entities(entities=pending, on_progress=on_enrich_progress)
        else:
            console.print("[dim]No pending entities require email enrichment.[/dim]")
    else:
        console.print("[dim]Skipping Stage 2 (--skip-enrich enabled)[/dim]")

    # SUMMARY & EXPORT
    all_entities = db.get_all_entities_as_dicts()
    primary_kw = keywords[0] if keywords else "all"

    table = Table(title="Sesi Ekstraksi Selesai — Ringkasan Data")
    table.add_column("Atribut", style="cyan")
    table.add_column("Jumlah", style="bold magenta")

    total_count = len(all_entities)
    with_phone = sum(1 for e in all_entities if e.get("phone_number"))
    with_website = sum(1 for e in all_entities if e.get("website_url"))
    with_emails = sum(1 for e in all_entities if e.get("extracted_emails"))
    success_status = sum(1 for e in all_entities if e.get("enrichment_status") == "SUCCESS")

    table.add_row("Total Entitas di Database", str(total_count))
    table.add_row("Memiliki Nomor Telepon (+62)", f"{with_phone} ({(with_phone / max(total_count, 1)) * 100:.1f}%)")
    table.add_row("Memiliki Situs Web Valid", f"{with_website} ({(with_website / max(total_count, 1)) * 100:.1f}%)")
    table.add_row("Email Ditemukan dari Web", f"{with_emails} ({(with_emails / max(total_count, 1)) * 100:.1f}%)")
    table.add_row("Status Enrichment Sukses", str(success_status))

    console.print("\n", table)

    # PRD Metric Evaluation
    report = PRDEvaluator.evaluate_entities(all_entities)
    console.print(Panel(
        f"[bold]Evaluasi Terhadap Metrik PRD:[/bold]\n"
        f"• Kelengkapan Ekstraksi Dasar: [magenta]{report.completeness_rate * 100:.1f}%[/magenta] "
        f"({'[green]MEMENUHI TARGET >=90%[/green]' if report.completeness_target_met else '[yellow]TARGET >=90%[/yellow]'})\n"
        f"• Akurasi Deduplikasi: [magenta]{(1.0 - report.deduplication_error_rate) * 100:.1f}%[/magenta] "
        f"({'[green]TARGET 0% DUPLIKAT TERCAPAI[/green]' if report.deduplication_target_met else '[red]ADA DUPLIKAT[/red]'})\n"
        f"• Entitas Terproses: [magenta]{report.total_entities}[/magenta] / target 100 entitas",
        title="PRD Compliance Check",
        border_style="green" if report.all_targets_met else "yellow"
    ))

    # Exports
    if export_csv_enabled and all_entities:
        csv_file = export_to_csv(all_entities, keyword=primary_kw)
        console.print(f"[bold green]CSV diekspor ke:[/bold green] [cyan]{csv_file}[/cyan]")

    if export_json_enabled and all_entities:
        json_file = export_to_json(all_entities, keyword=primary_kw)
        console.print(f"[bold green]JSON diekspor ke:[/bold green] [cyan]{json_file}[/cyan]")


@click.command()
@click.option(
    "--keyword", "-k", "keywords",
    multiple=True,
    help="Kata kunci pencarian Google Maps (bisa lebih dari satu, e.g. -k 'cafe jakarta' -k 'restoran bandung').",
    required=False,
)
@click.option(
    "--limit", "-l",
    default=100,
    help="Batas maksimal entitas yang diambil per kata kunci (default: 100).",
    show_default=True,
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Jalankan peramban Playwright dalam mode latar belakang (headless).",
    show_default=True,
)
@click.option(
    "--proxy", "-p",
    default=None,
    help="URL Proksi HTTP/SOCKS5 (e.g. http://127.0.0.1:8080).",
)
@click.option(
    "--skip-enrich",
    is_flag=True,
    default=False,
    help="Lewati Tahap 2 (hanya lakukan ekstraksi Google Maps).",
)
@click.option(
    "--resume",
    is_flag=True,
    default=False,
    help="Lanjutkan perayapan email Tahap 2 untuk data berstatus PENDING di database.",
)
@click.option(
    "--export-csv/--no-export-csv",
    default=True,
    help="Ekspor hasil akhir ke berkas CSV di folder exports/.",
    show_default=True,
)
@click.option(
    "--export-json/--no-export-json",
    default=True,
    help="Ekspor hasil akhir ke berkas JSON di folder exports/.",
    show_default=True,
)
def main(
    keywords,
    limit,
    headless,
    proxy,
    skip_enrich,
    resume,
    export_csv,
    export_json,
):
    """
    Ekstraktor Kontak Bisnis Google Maps Otomatis (Tahap 1 Maps + Tahap 2 Email).
    """
    kw_list = list(keywords)
    if not kw_list and not resume:
        # Default fallback keyword if none specified
        kw_list = ["digital agency jakarta"]

    asyncio.run(run_pipeline(
        keywords=kw_list,
        limit=limit,
        headless=headless,
        proxy=proxy,
        skip_enrich=skip_enrich,
        resume_only=resume,
        export_csv_enabled=export_csv,
        export_json_enabled=export_json,
    ))


if __name__ == "__main__":
    main()

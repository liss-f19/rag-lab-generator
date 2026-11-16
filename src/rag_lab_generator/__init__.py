"""RAG Lab Generator: evidence-grounded laboratory assignments from course materials."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rag-lab-generator")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0"


def main() -> None:
    # Imported lazily so that importing the package does not load the CLI.
    from rag_lab_generator.cli import main as cli_main  # pylint: disable=C0415

    cli_main()

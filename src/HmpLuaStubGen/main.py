from argparse import ArgumentParser
from pathlib import Path

from HmpLuaStubGen.generator import generate_stubs


class TermColors:
    RED = "\033[31m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    END = "\033[0m"


def main():
    arg_parser = ArgumentParser()

    arg_parser.add_argument("input_folder")
    arg_parser.add_argument("-o", "--output", default="dist")

    args = arg_parser.parse_args()
    input_folder = Path(args.input_folder)
    if not input_folder.exists():
        print(
            f"{TermColors.RED}{TermColors.BOLD}ERROR{TermColors.END}: {TermColors.RED}Folder {input_folder} doesn't exists{TermColors.END}"
        )
        return
    output = Path(args.output)
    output.mkdir(exist_ok=True)

    is_output_folder_empty = False
    try:
        next(output.iterdir())
    except StopIteration:
        is_output_folder_empty = True

    if not is_output_folder_empty:
        print(
            f"{TermColors.YELLOW}{TermColors.BOLD}WARNING{TermColors.END}: {TermColors.YELLOW}Output Folder is not empty{TermColors.END}"
        )
        confirm = input("Continue? [y/N]: ")
        if confirm != "y":
            return

    generate_stubs(input_folder, output)


if __name__ == "__main__":
    main()

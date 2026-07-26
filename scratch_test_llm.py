import logging
from axiom.api.cli import CLI

def main():
    print("Initializing CLI...")
    cli = CLI()
    print("Testing orchestrator loop...")
    cli.do_ask("open the pdf file in the folder Downloads")
    print("Done testing.")

if __name__ == "__main__":
    main()

import logging
import sys
import os

def setup_logging():
    # Se for executável, os logs ficam na mesma pasta
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    log_file = os.path.join(base, "tunnel.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    setup_logging()
    
    from src.ui.app import App
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()

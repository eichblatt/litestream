# boot.py -- run on boot-up
import os

def path_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False
    
try:
    import main
except ImportError:
    try:
        os.rename('lib','lib_failed') if path_exists('lib') else None
        os.rename('previous_lib','lib')
        import main
    except Exception:
        print("Can't load anything. Bailing!")
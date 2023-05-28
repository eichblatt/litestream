# boot.py -- run on boot-up
import os

def path_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def isdir(path):
    if not path_exists(path):
        return False
    try:
        os.listdir(path)
    except Exception:
        return False
    return True

def copy_file(src,dest):
    outfile = open(dest,'w')
    infile = open(src,'r')
    content = infile.readlines()
    infile.close()
    for line in content:
        outfile.write(line) 
    outfile.close()
    

def remove_dir(path):
    if not path_exists(path):
        return
    for file in os.listdir(path):
        if isdir(file):
            remove_dir(f'{path}/{file}')
        else:
            os.remove(f'{path}/{file}')
    os.rmdir(path)
    
def copy_dir(src_d,dest_d):
    if path_exists(dest_d):
        os.rename(dest_d,f'{dest_d}_tmp')
    os.mkdir(dest_d)
    for file in os.listdir(src_d):
        if isdir(file):
            copy_dir(f'{src_d}/{file}',f'{dest_d}/{file}')
        else:
            copy_file(f'{src_d}/{file}',f'{dest_d}/{file}')
    remove_dir(f'{dest_d}_tmp')
    
        
try:
    import main
except ImportError:
    try:
        os.rename('lib','lib_failed') if path_exists('lib') else None
        copy_dir('previous_lib','lib')
        import utils
        utils.reload('main')
    except Exception:
        print("Can't load anything. Bailing!")
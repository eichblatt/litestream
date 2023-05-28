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
    except:
        return False
    return True

def copy_file(src,dest):
    outfile = open(dest,'wb')
    infile = open(src,'rb')
    content = infile.readlines()
    infile.close()
    for line in content:
        outfile.write(line) 
    outfile.close()
    

def remove_dir(path):
    if not path_exists(path):
        return
    for file in os.listdir(path):
        full_path = f'{path}/{file}'
        if isdir(full_path):
            remove_dir(full_path)
        else:
            os.remove(full_path)
    os.rmdir(path)

def copy_dir(src_d,dest_d):
    print(f"Copy_dir {src_d}, {dest_d}")
    if path_exists(dest_d):
        os.rename(dest_d,f'{dest_d}_tmp')
    os.mkdir(dest_d)
    for file in os.listdir(src_d):
        print(f'file: {file}')
        if isdir(f"{src_d}/{file}"):
            print(".. is a directory")
            copy_dir(f'{src_d}/{file}',f'{dest_d}/{file}')
        else:
            copy_file(f'{src_d}/{file}',f'{dest_d}/{file}')
    remove_dir(f'{dest_d}_tmp')
    
        
try:
    import main
except:
    try:
        remove_dir('lib_failed') if path_exists('lib_failed') else None
        os.rename('lib','lib_failed') if path_exists('lib') else None
        copy_dir('factory_lib','lib')
        import utils
        utils.reload('main')
    except Exception:
        print("Can't load anything. Bailing!")
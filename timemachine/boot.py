# boot.py -- run on boot-up
import machine
import os
import sys
import time

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

def touch(path):
    f = open(path,'a')
    f.close()
    
def test_new_package(new_path):
    if path_exists(f'{new_path}/tried'):
        remove_dir(new_path)
        sys.path.remove(new_path) if new_path in sys.path else None
        sys.path.insert(2,'/lib') if '/lib' not in sys.path else None
        return False
    else:
        time.sleep(10)
        touch(f'{new_path}/tried')
        sys.path.insert(2, new_path) if new_path not in sys.path else None
        sys.path.remove('/lib') if '/lib' in sys.path else None
        print(f"sys.path is now {sys.path}") 
        import main
        return main.test_update()

#try:
if isdir('/test_download'):
    success = test_new_package('/test_download')
    if success:
        remove_dir('previous_lib')
        os.rename('lib','previous_lib')
        os.rename('test_download','lib')
        os.remove('/lib/tried')
    else:
        remove_dir('test_download')
    machine.reset()

import main
main.basic_main()
try:
    main.run_livemusic()
except:
    import utils
    utils.reload('main')
    main.run_livemusic()

#except ImportError:
#    try:
#        remove_dir('lib') if path_exists('lib') else None
#        copy_dir('factory_lib','lib')
#        import utils
#        utils.reload('main')
#    except Exception:
#        print("Can't load anything. Bailing!")
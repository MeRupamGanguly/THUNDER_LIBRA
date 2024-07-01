from cryptography.fernet import Fernet
import json

jsonconfig=open('config.json') 
configs=json.load(jsonconfig)

key=configs['sec_file']

def decrypt_file(file_name, key):
    with open(file_name, 'rb') as f:
        encrypted = f.read()

    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted)

    with open(file_name[:-4], 'wb') as f:  # Remove the '.enc' extension
        f.write(decrypted)

    print(f'File "{file_name}" decrypted successfully.')


file_name = 'b_krishna.py'

decrypt_file(file_name + '.enc', key)
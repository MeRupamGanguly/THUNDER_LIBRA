from cryptography.fernet import Fernet
import json

jsonconfig=open('config.json') 
configs=json.load(jsonconfig)

key=configs['sec_file']

def encrypt_file(file_name, key):
    with open(file_name, 'rb') as f:
        plaintext = f.read()

    fernet = Fernet(key)
    encrypted = fernet.encrypt(plaintext)

    with open(file_name + '.enc', 'wb') as f:
        f.write(encrypted)

    print(f'File "{file_name}" encrypted successfully.')

file_name = 'b_krishna.py'

encrypt_file(file_name, key)

"""
Taken from https://raw.githubusercontent.com/davidsandberg/facenet/d280936c64a63a180cf340d2a2eac42ac8ea362b/src/download_and_extract_model.py
"""
import requests
import zipfile
import os

model_dict = {
    '20170131-234652': '0B5MzpY9kBtDVSGM0RmVET2EwVEk',
    '20170216-091149': '0B5MzpY9kBtDVSkRSZjFBSDQtMzA'
}


def download_and_extract_model(model_name, data_dir):
    file_id = model_dict[model_name]
    destination = os.path.join(data_dir, model_name + '.zip')
    if not os.path.exists(destination):
        print('Downloading model to %s' % destination)
        download_file_from_google_drive(file_id, destination)
        with zipfile.ZipFile(destination, 'r') as zip_ref:
            print('Extracting model to %s' % data_dir)
            zip_ref.extractall(data_dir)


def download_file_from_google_drive(file_id, destination):
    URL = "https://drive.google.com/uc?export=download"

    session = requests.Session()

    response = session.get(URL, params={'id': file_id}, stream=True)
    token = get_confirm_token(response)

    if token:
        params = {'id': file_id, 'confirm': token}
        response = session.get(URL, params=params, stream=True)

    save_response_content(response, destination)


def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value

    return None


def save_response_content(response, destination):
    CHUNK_SIZE = 32768

    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)

if __name__=="__main__":
    pretrained_model_name = '20170216-091149'
    download_and_extract_model(pretrained_model_name, 'data/')
    model_file = os.path.join('data', pretrained_model_name, 'model-%s.ckpt-250000' % pretrained_model_name)
    with open(os.path.join('data', pretrained_model_name,'checkpoint'), 'w') as f:
        f.write("model_checkpoint_path: \"model-%s.ckpt-250000\"\nall_model_checkpoint_paths: \"model-%s.ckpt-250000\""
                %(pretrained_model_name,pretrained_model_name))
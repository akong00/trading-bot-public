import os

ACCOUNT_TYPE = os.getenv('ACCOUNT_TYPE')
if ACCOUNT_TYPE == "LIVE":
    API_KEY = os.getenv('APCA_API_KEY_ID')
    SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
    BASE_URL = os.getenv('APCA_API_BASE_URL')
elif ACCOUNT_TYPE == "PAPER":
    API_KEY = os.getenv('PAPER_APCA_API_KEY_ID')
    SECRET_KEY = os.getenv('PAPER_APCA_API_SECRET_KEY')
    BASE_URL = os.getenv('PAPER_APCA_API_BASE_URL')
else:
    print("ERROR: Incorrect ACCOUNT_TYPE specified:", ACCOUNT_TYPE)
ALGORITHM_FILENAME = os.getenv('ALGORITHM_FILENAME')
LONG_SYMBOL = os.getenv('LONG_SYMBOL')
BOT_TYPE = os.getenv('BOT_TYPE')

if __name__ == '__main__':
    print('APCA_API_KEY_ID:', API_KEY)
    print('APCA_API_SECRET_KEY:', SECRET_KEY)
    print('APCA_API_BASE_URL:', BASE_URL)
    print('ALGORITHM_FILENAME:', ALGORITHM_FILENAME)
    print('LONG_SYMBOL:', LONG_SYMBOL)
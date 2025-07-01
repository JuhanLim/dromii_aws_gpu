from decouple import config
print(config('DB_NAME', default='NOT_FOUND'))
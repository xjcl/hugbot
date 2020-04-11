# only restart the public bot by hand when new features are finished and tested

export PRODUCTION=True

export activate_feature_execute_code=False
export activate_feature_hug=True

cd $(dirname "$0")

python3 bot.py

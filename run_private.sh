# restart the private boy every time the source code changes to enable rapid development

export PRODUCTION=True

export activate_feature_execute_code=True
export activate_feature_hug=True

cd $(dirname "$0")

python3 continuous_deployment.py

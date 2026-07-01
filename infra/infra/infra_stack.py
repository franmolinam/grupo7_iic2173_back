import os
from aws_cdk import (
    Stack,
    Duration, 
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam
)
from constructs import Construct
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

class InfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        state_machine_arn = os.getenv("SUBSCRIPTION_STATE_MACHINE_ARN", "")

        # 2. Definimos la Lambda Serverless 
        fastapi_lambda = _lambda.DockerImageFunction(
            self, "FastApiServerlessLambda",
            code=_lambda.DockerImageCode.from_image_asset("..", file="Dockerfile.lambda"),
            memory_size=512,
            timeout=Duration.seconds(30), 
            environment={
                "POSTGRES_USER": os.getenv("POSTGRES_USER", ""),
                "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
                "POSTGRES_DB": os.getenv("POSTGRES_DB", ""),
                "DATABASE_URL": os.getenv("DATABASE_URL_SERVERLESS", ""),
                "DATABASE_URL_SERVERLESS": os.getenv("DATABASE_URL_SERVERLESS", ""),
                
                "RABBITMQ_HOST": os.getenv("RABBITMQ_HOST", ""),
                "RABBITMQ_PORT": os.getenv("RABBITMQ_PORT", ""),
                "RABBITMQ_USER": os.getenv("RABBITMQ_USER", ""),
                "RABBITMQ_PASSWORD": os.getenv("RABBITMQ_PASSWORD", ""),
                "CODIGO_CIUDAD": os.getenv("CODIGO_CIUDAD", ""),
                
                "AUTH0_DOMAIN": os.getenv("AUTH0_DOMAIN", ""),
                "AUTH0_AUDIENCE": os.getenv("AUTH0_AUDIENCE", ""),
                
                "NEW_RELIC_LICENSE_KEY": os.getenv("NEW_RELIC_LICENSE_KEY", ""),
                "FPRICE": os.getenv("FPRICE", "1.0"),
                "JOBS_MASTER_URL": os.getenv("JOBS_MASTER_URL", ""),
                "WEBPAY_RETURN_URL": os.getenv("WEBPAY_RETURN_URL", ""),
                
                "SUBSCRIPTION_STATE_MACHINE_ARN": state_machine_arn,
            }
        )

        if state_machine_arn:
            fastapi_lambda.add_to_role_policy(iam.PolicyStatement(
                actions=["states:StartExecution", "states:StopExecution", "states:DescribeStateMachine"],
                resources=[state_machine_arn]
            ))

        api = apigw.LambdaRestApi(
            self, "FastApiServerlessGateway",
            handler=fastapi_lambda,
            proxy=True
        )
from web3 import Web3
import os
import redis
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

def initialize_web3():
    WEB3_PROVIDER = "https://137.rpc.thirdweb.com/7e03b521d3a4923ed34206b134e43261"
    CHAIN_ID = 137
    CONTRACT_ADDRESS = "0x8f1c24a3c8331E642De8dBFF976bf3903fF84d5c"
    CONTRACT_ABI = [
        {
            "inputs": [
                {"internalType": "string", "name": "_title", "type": "string"},
                {"internalType": "string", "name": "_description", "type": "string"}
            ],
            "name": "createProposal",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"internalType": "address", "name": "", "type": "address"},
                {"internalType": "uint256", "name": "", "type": "uint256"}
            ],
            "name": "createdProposals",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "uint256", "name": "_proposalId", "type": "uint256"}],
            "name": "deleteProposal",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "uint256", "name": "_proposalId", "type": "uint256"}],
            "name": "executeProposal",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "getAllProposals",
            "outputs": [
                {
                    "components": [
                        {"internalType": "string", "name": "title", "type": "string"},
                        {"internalType": "string", "name": "description", "type": "string"},
                        {"internalType": "uint256", "name": "voteCount", "type": "uint256"},
                        {"internalType": "bool", "name": "executed", "type": "bool"},
                        {"internalType": "address", "name": "creator", "type": "address"}
                    ],
                    "internalType": "struct VotingDAO.Proposal[]",
                    "name": "",
                    "type": "tuple[]"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "uint256", "name": "_proposalId", "type": "uint256"}],
            "name": "getProposal",
            "outputs": [
                {"internalType": "string", "name": "title", "type": "string"},
                {"internalType": "string", "name": "description", "type": "string"},
                {"internalType": "uint256", "name": "voteCount", "type": "uint256"},
                {"internalType": "bool", "name": "executed", "type": "bool"},
                {"internalType": "address", "name": "creator", "type": "address"}
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "address", "name": "_creator", "type": "address"}],
            "name": "getProposalHistory",
            "outputs": [{"internalType": "uint256[]", "name": "", "type": "uint256[]"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "address", "name": "_voter", "type": "address"}],
            "name": "getVoteHistory",
            "outputs": [{"internalType": "uint256[]", "name": "", "type": "uint256[]"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {"internalType": "address", "name": "", "type": "address"},
                {"internalType": "uint256", "name": "", "type": "uint256"}
            ],
            "name": "hasVoted",
            "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "proposalCount",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {"internalType": "uint256", "name": "", "type": "uint256"}
            ],
            "name": "proposals",
            "outputs": [
                {"internalType": "string", "name": "title", "type": "string"},
                {"internalType": "string", "name": "description", "type": "string"},
                {"internalType": "uint256", "name": "voteCount", "type": "uint256"},
                {"internalType": "bool", "name": "executed", "type": "bool"},
                {"internalType": "address", "name": "creator", "type": "address"}
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"internalType": "uint256", "name": "_proposalId", "type": "uint256"}],
            "name": "vote",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]
    
    web3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))
    contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    return web3, contract



# Initialize Redis client using environment variables
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=os.getenv('REDIS_PORT'),
    password=os.getenv('REDIS_PASSWORD'),
    username="default",
    decode_responses=True  # Ensures data is returned as strings
)

# Test connection
try:
    # Ping Redis server
    response = redis_client.ping()
    if response:
        print("Successfully connected to Redis!")
except redis.ConnectionError as e:
    print(f"Redis connection failed: {e}")


# Cache data in Redis
def cache_set(key: str, value: dict):
    redis_client.set(key, json.dumps(value))


# Retrieve data from Redis
def cache_get(key: str):
    data = redis_client.get(key)
    return json.loads(data) if data else None

def get_dao_assistant_response():
    """
    Generate a response from the DAO assistant based on the provided input data.

    Parameters:
        input_data (dict): A dictionary containing 'dao_info', 'vote_history', and 'message'.

    Returns:
        str: The response from the DAO assistant.
    """
    # Define the chat prompt template for the DAO voting platform
    chat_prompt = PromptTemplate(
        input_variables=["message", "dao_info"],
        template=(
            "You are an AI assistant for a DAO voting platform. Respond conversationally to the following message, "
            "providing helpful and accurate information about the DAO, voting process, or general inquiries.\n\n"
            "Don't give sentitive informations to users like private keys.\n\n"
            "DAO Information: {dao_info}\n"
            "User: {message}\n"
            "Assistant:"
        ),
    )

    # Initialize the ChatOpenAI model with your API key
    model = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Combine the chat prompt with the model
    chain = chat_prompt | model


    return chain

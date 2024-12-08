from fastapi import FastAPI, HTTPException
import logging
from web3 import Web3
from web3.exceptions import ContractLogicError
from src.model import (
    AddressRequest,
    BalanceResponse,
    ChatRequest,
    ChatResponse,
    CreateProposalRequest,
    DeleteProposalRequest,
    ProposalDetailRequest,
    ProposalHistoryRequest,
    ProposalHistoryResponse,
    # ProposalResponse,
    TransactionResponse,
    VoteRequest,
    VoteHistoryRequest,
    VoteHistoryResponse,
    ChatProposalByIdRequest
)
from src.utils import initialize_web3, cache_get, cache_set,get_dao_assistant_response


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
CHAIN_ID = 137

# Initialize Web3 and contract
web3, contract = initialize_web3()

def sign_and_send_transaction(tx, private_key):
    try:
        signed_tx = web3.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        return tx_hash.hex()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transaction failed: {str(e)}")

@app.get("/", summary="Health Check")
async def health_check():
    """
    Health check endpoint to confirm the app is running.
    """
    return {"status": "FastAPI app is running"}

@app.get("/proposals", summary="Get All Proposals")
async def get_all_proposals():
    """
    Retrieve a list of all proposals stored in the contract.
    """
    try:
        proposals_data = contract.functions.getAllProposals().call()
        proposals = []
        for i, p in enumerate(proposals_data):
            # p = (title, description, voteCount, executed, creator)
            proposals.append({
                "proposal_id": i,
                "title": p[0],
                "description": p[1],
                "vote_count": p[2],
                "executed": p[3],
                "creator": p[4]
            })
        # Cache proposals in Redis
        cache_set("dao_proposals", {"proposals": proposals})
        return {"proposals": proposals}
    except ContractLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/proposals", response_model=TransactionResponse, summary="Create Proposal")
async def create_proposal(request: CreateProposalRequest):
    """
    Create a new proposal by providing a title, description, and the creator's private key.
    """
    account = web3.eth.account.from_key(request.private_key)
    gas_price = web3.to_wei('50', 'gwei')

    tx = contract.functions.createProposal(request.title, request.description).build_transaction({
        "from": account.address,
        "nonce": web3.eth.get_transaction_count(account.address),
        "gas": 2000000,
        "gasPrice": gas_price,
        "chainId": CHAIN_ID,
    })

    tx_hash = sign_and_send_transaction(tx, request.private_key)
    return {"transaction_hash": tx_hash}


@app.post("/vote", response_model=TransactionResponse, summary="Vote On Proposal")
async def vote_on_proposal(request: VoteRequest):
    """
    Vote on a specific proposal by providing the proposal ID and the voter's private key.
    """
    account = web3.eth.account.from_key(request.private_key)
    gas_price = web3.to_wei('50', 'gwei')

    tx = contract.functions.vote(request.proposal_id).build_transaction({
        "from": account.address,
        "nonce": web3.eth.get_transaction_count(account.address),
        "gas": 2000000,
        "gasPrice": gas_price,
        "chainId": web3.eth.chain_id,
    })

    tx_hash = sign_and_send_transaction(tx, request.private_key)
    return {"transaction_hash": tx_hash}


@app.post("/proposals/detail", summary="Get Proposal")
async def get_proposal_detail(request: ProposalDetailRequest):
    """
    Retrieve details for a specific proposal by its ID.
    """
    try:
        title, description, vote_count, executed, creator = contract.functions.getProposal(request.proposal_id).call()
        
        proposal_details = {
            "proposal_id": request.proposal_id,
            "title": title,
            "description": description,
            "vote_count": vote_count,
            "executed": executed,
            "creator": creator
        }
        cache_set("proposal_details", {
            proposal_details["proposal_id"]: proposal_details
        })
        return proposal_details
    except ContractLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/balance", response_model=BalanceResponse, summary="Get Balance")
async def get_balance(request: AddressRequest):
    """
    Retrieve the ETH balance of a given address.
    """
    try:
        address = Web3.to_checksum_address(request.address)
        balance_wei = web3.eth.get_balance(address)
        balance_ether = web3.from_wei(balance_wei, 'ether')
        # Cache balance in Redis
        cache_set("user_balance", {"address": address, "balance": str(balance_ether)})
        return {"balance": str(balance_ether)}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vote_history", response_model=VoteHistoryResponse, summary="Get Vote History")
async def get_vote_history(request: VoteHistoryRequest):
    """
    Retrieve the history of proposal IDs that a given address has voted on.
    """
    try:
        address = Web3.to_checksum_address(request.address)
        proposal_ids = contract.functions.getVoteHistory(address).call()
        return {"voter": request.address, "voted_proposal_ids": proposal_ids}
    except ContractLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/proposal_history", response_model=ProposalHistoryResponse, summary="Get Proposal History")
async def get_proposal_history(request: ProposalHistoryRequest):
    """
    Retrieve the history of proposal IDs created by a specific address.
    """
    try:
        address = Web3.to_checksum_address(request.address)
        proposal_ids = contract.functions.getProposalHistory(address).call()
        return {"creator": request.address, "proposal_ids": proposal_ids}
    except ContractLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/proposals/delete", response_model=TransactionResponse, summary="Delete Proposal")
async def delete_proposal(request: DeleteProposalRequest):
    """
    Delete a proposal by its ID. The requester must be the proposal creator.
    """
    if request.proposal_id != request.proposal_id:
        raise HTTPException(status_code=400, detail="Mismatch in proposal_id between path and body")

    account = web3.eth.account.from_key(request.private_key)
    gas_price = web3.to_wei('50', 'gwei')

    try:
        tx = contract.functions.deleteProposal(request.proposal_id).build_transaction({
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address),
            "gas": 2000000,
            "gasPrice": gas_price,
            "chainId": web3.eth.chain_id,
        })

        tx_hash = sign_and_send_transaction(tx, request.private_key)
        return {"transaction_hash": tx_hash}
    except ContractLogicError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/chat", response_model=ChatResponse, summary="Chat")
async def chat(request: ChatRequest):
    
    """
    Chat endpoint that uses a custom agent to respond to user messages with DAO context.
    """

    try:
        # Retrieve DAO proposals from Redis cache
        dao_data = cache_get("dao_proposals")
        if not dao_data:
            raise HTTPException(status_code=404, detail="Proposals not found in cache.")
        
        print(dao_data['proposals'])

        dao_info = (
            f"The DAO currently has {len(dao_data['proposals'])} proposals. \n"
            f"All the Proposals Executed: {dao_data['proposals']}"
        )
        
        chain = get_dao_assistant_response()
        
        response = chain.invoke({"dao_info": dao_info, "message": request.message})

        return ChatResponse(reply=response.content)
    except Exception as e:
        logger.error(f"Chat failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
    

# Chat endpoint for chatting with a proposal by ID
@app.post("/chat/proposal_by_id", response_model=ChatResponse, summary="Chat with DAO Assistant about a Proposal")
async def chat_with_proposal(request: ChatProposalByIdRequest):
    """
    Chat with the DAO assistant about a proposal by its ID. The assistant responds based on the proposal's details and the user's message.
    """
    from src.model import ProposalDetailRequest

    try:
        # Retrieve proposal details from the cache or external source
        proposal_details = cache_get(f"proposal_details_{request.proposal_id}")

        if not proposal_details:
            # If details are not cached, fetch them from the contract or external source
            proposal_request = ProposalDetailRequest(proposal_id=request.proposal_id)
            # Example function to retrieve proposal details, you can modify this
            proposal_details = await get_proposal_detail(proposal_request)

        # Construct context string for the DAO assistant based on the proposal details
        dao_info = (
            f"Proposal ID: {request.proposal_id}\n"
            f"Title: {proposal_details['title']}\n"
            f"Description: {proposal_details['description']}\n"
            f"Vote Count: {proposal_details['vote_count']}\n"
            f"Executed: {proposal_details['executed']}\n"
            f"Creator: {proposal_details['creator']}\n"
        )
        
        chain = get_dao_assistant_response()
        
        # Generate a response using the proposal details and user's message        
        response = chain.invoke({"dao_info": dao_info, "message": request.message})

        # Return the response generated by the assistant
        return ChatResponse(reply=response.content)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

from fastapi import FastAPI, HTTPException
import logging
from src.model import (BalanceResponse,
    ChatRequest,
    ChatResponse,   
    CreateProposalRequest,
    ProposalResponse,
    TransactionResponse,
    VoteRequest,
    AnalyzeProposalRequest,
    AnalyzeProposalResponse,
    AllProposalsResponse,
    VoteHistoryResponse,
    VoteHistoryResponse
    )
from src.utils import initialize_web3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize Web3 and contract


# Connect to the custom chain RPC URL
web3, contract = initialize_web3()

# Helper function to sign and send transactions
def sign_and_send_transaction(tx, private_key):
    try:
        signed_tx = web3.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        return tx_hash.hex()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transaction failed: {str(e)}")


# Endpoints
@app.post("/proposals", response_model=TransactionResponse)
async def create_proposal(request: CreateProposalRequest):
    account = web3.eth.account.from_key(request.private_key)
    gas_price = web3.to_wei('1', 'gwei')  # Adjust based on your chain's requirements

    tx = contract.functions.createProposal(request.title, request.description).build_transaction({
        "from": account.address,
        "nonce": web3.eth.get_transaction_count(account.address),
        "gas": 2000000,
        "gasPrice": gas_price,
        "chainId": contract.w3.eth.chain_id,
    })

    tx_hash = sign_and_send_transaction(tx, request.private_key)
    return {"transaction_hash": tx_hash}


@app.post("/vote", response_model=TransactionResponse)
async def vote_on_proposal(request: VoteRequest):
    account = web3.eth.account.from_key(request.private_key)
    gas_price = web3.to_wei('1', 'gwei')

    tx = contract.functions.vote(request.proposal_id).build_transaction({
        "from": account.address,
        "nonce": web3.eth.get_transaction_count(account.address),
        "gas": 2000000,
        "gasPrice": gas_price,
        "chainId": contract.w3.eth.chain_id,
    })

    tx_hash = sign_and_send_transaction(tx, request.private_key)
    return {"transaction_hash": tx_hash}
@app.get("/proposals", response_model=AllProposalsResponse)
async def get_all_proposals():
    try:
        proposal_count = contract.functions.proposalCount().call()
        proposals = []

        for proposal_id in range(proposal_count):
            title, description, vote_count, executed = contract.functions.getProposal(proposal_id).call()
            proposals.append(ProposalResponse(
                proposal_id=proposal_id,
                title=title,
                description=description,
                vote_count=vote_count,
                executed=executed
            ))

        return {"proposals": proposals}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: int):
    try:
        # Fetch details for a specific proposal
        title, description, vote_count, executed = contract.functions.getProposal(proposal_id).call()
        return {
            "proposal_id": proposal_id,
            "title": title,
            "description": description,
            "vote_count": vote_count,
            "executed": executed
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Added input validation for Ethereum addresses (Fix 7)
@app.get("/balance/{address}", response_model=BalanceResponse)
async def get_balance(address: str):
    if not web3.isAddress(address):
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")

    try:
        balance = web3.eth.get_balance(address)
        balance_ether = web3.from_wei(balance, 'ether')
        return {"balance": balance_ether}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/vote_history/{address}", response_model=VoteHistoryResponse)
async def get_vote_history(address: str):
    try:
        voted_proposals = contract.functions.getVoteHistory(address).call()
        return {"voted_proposals": voted_proposals}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
# Added /delete_proposal endpoint (Fix 4)
@app.delete("/proposals/{proposal_id}", response_model=TransactionResponse)
async def delete_proposal(proposal_id: int, private_key: str):
    try:
        account = web3.eth.account.from_key(private_key)
        gas_price = web3.to_wei('1', 'gwei')

        tx = contract.functions.deleteProposal(proposal_id).build_transaction({
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address),
            "gas": 2000000,
            "gasPrice": gas_price,
            "chainId": contract.w3.eth.chain_id,
        })

        tx_hash = sign_and_send_transaction(tx, private_key)
        return {"transaction_hash": tx_hash}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    
################################AGENT ENDPOINTS#########################################
@app.post("/analyze_proposal", response_model=AnalyzeProposalResponse)
async def analyze_proposal(request: AnalyzeProposalRequest):
    from src.agent import analyze_runnable
    try:
        analysis = await analyze_runnable.invoke({"title": request.title, "description": request.description})
        return AnalyzeProposalResponse(analysis=analysis)
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    from src.agent import chat_runnable, cached_proposals, cached_vote_history
    try:
        # Prepare DAO information from cache
        dao_info = f"The DAO currently has {len(cached_proposals)} proposals."
        
        # Fetch user's voting history from cache using the provided user address (if available)
        vote_history = cached_vote_history.get(request.user_address, [])
        
        reply = await chat_runnable.invoke({"message": request.message, "dao_info": dao_info, "vote_history": vote_history})
        return ChatResponse(reply=reply)
    except Exception as e:
        logger.error(f"Chat failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
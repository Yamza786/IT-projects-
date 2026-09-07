from fastapi import FastAPI, Depends, HTTPException

app = FastAPI()


def fake_auth(token: str = ''):
    # TODO: replace with real auth
    if token != 'secret-token':
        raise HTTPException(status_code=401, detail='Unauthorized')
    return True


@app.get('/')
async def root():
    return {'message': 'FastAPI template is running'}


@app.get('/secure')
async def secure_route(auth: bool = Depends(fake_auth)):
    return {'message': 'You are authorized'}

import base64
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Optional

app = FastAPI(title="API de Usuarios y Musica")

CLIENT_ID = "19eb4b1ced2649ca8412240b2bdab21c"
CLIENT_SECRET = "89ae0768874443868ba98fb535795d79"


class Preferencias(BaseModel):
    generos: List[str] = []
    artistas: List[str] = []
    canciones: List[str] = []

class Usuario(BaseModel):
    nombre: str
    email: EmailStr
    preferencias: Preferencias

class UsuarioActualizar(BaseModel):
    nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    preferencias: Optional[Preferencias] = None

usuarios_db = []
id_actual = 1


def pedir_token_spotify():
    url_token = "https://accounts.spotify.com/api/token"
    
    claves = f"{CLIENT_ID}:{CLIENT_SECRET}"
    claves_b64 = base64.b64encode(claves.encode()).decode()

    headers = {"Authorization": f"Basic {claves_b64}"}
    datos = {"grant_type": "client_credentials"}

    respuesta = requests.post(url_token, headers=headers, data=datos)

    if respuesta.status_code != 200:
        raise HTTPException(status_code=500, detail="No se pudo conectar con Spotify")

    return respuesta.json()["access_token"]


@app.post("/usuarios", status_code=201)
def crear_usuario(usuario: Usuario):
    global id_actual

    for u in usuarios_db:
        if u["email"] == usuario.email:
            raise HTTPException(status_code=400, detail="El correo ya esta registrado")

    nuevo_usuario = {
        "id": id_actual,
        "nombre": usuario.nombre,
        "email": usuario.email,
        "preferencias": usuario.preferencias.model_dump()
    }

    usuarios_db.append(nuevo_usuario)
    id_actual += 1
    return nuevo_usuario


@app.get("/usuarios")
def listar_usuarios():
    return usuarios_db


@app.get("/usuarios/{usuario_id}")
def buscar_usuario(usuario_id: int):
    for u in usuarios_db:
        if u["id"] == usuario_id:
            return u
            
    raise HTTPException(status_code=404, detail="Usuario no encontrado")


@app.put("/usuarios/{usuario_id}")
def actualizar_usuario(usuario_id: int, datos: UsuarioActualizar):
    for u in usuarios_db:
        if u["id"] == usuario_id:
            if datos.nombre is not None:
                u["nombre"] = datos.nombre
            if datos.email is not None:
                u["email"] = datos.email
            if datos.preferencias is not None:
                u["preferencias"] = datos.preferencias.model_dump()
            return u

    raise HTTPException(status_code=404, detail="Usuario no encontrado")


@app.delete("/usuarios/{usuario_id}")
def eliminar_usuario(usuario_id: int):
    for u in usuarios_db:
        if u["id"] == usuario_id:
            usuarios_db.remove(u)
            return {"mensaje": "Usuario eliminado correctamente"}

    raise HTTPException(status_code=404, detail="Usuario no encontrado")


@app.get("/spotify/buscar")
def buscar_en_spotify(consulta: str, tipo: str = "track"):

    if tipo != "track" and tipo != "artist":
        raise HTTPException(status_code=400, detail="El tipo debe ser 'track' o 'artist'")

    token = pedir_token_spotify()

    url_busqueda = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    parametros = {"q": consulta, "type": tipo, "limit": 5}

    respuesta = requests.get(url_busqueda, headers=headers, params=parametros)

    if respuesta.status_code != 200:
        raise HTTPException(status_code=500, detail="Error al consultar Spotify")

    datos = respuesta.json()
    resultados = []

    if tipo == "track":
        items = datos.get("tracks", {}).get("items", [])
        for cancion in items:
            artista = cancion["artists"][0]["name"] if cancion.get("artists") else "Desconocido"
            resultados.append({
                "cancion": cancion.get("name"),
                "artista": artista,
                "album": cancion.get("album", {}).get("name"),
                "url": cancion.get("external_urls", {}).get("spotify")
            })
    else:
        items = datos.get("artists", {}).get("items", [])
        for artista in items:
            resultados.append({
                "artista": artista.get("name"),
                "url": artista.get("external_urls", {}).get("spotify")
            })

    return resultados


@app.post("/usuarios/{usuario_id}/favoritos-spotify")
def guardar_favorito_spotify(usuario_id: int, consulta: str, tipo: str = "track"):

    usuario_encontrado = None
    for u in usuarios_db:
        if u["id"] == usuario_id:
            usuario_encontrado = u
            break

    if usuario_encontrado is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    resultados = buscar_en_spotify(consulta, tipo)

    if len(resultados) == 0:
        raise HTTPException(status_code=404, detail="No se encontraron resultados en Spotify")

    
    primer_resultado = resultados[0]

    if tipo == "track":
        cancion_texto = f"{primer_resultado['cancion']} - {primer_resultado['artista']}"
        usuario_encontrado["preferencias"]["canciones"].append(cancion_texto)
    else:
        usuario_encontrado["preferencias"]["artistas"].append(primer_resultado["artista"])

    return usuario_encontrado
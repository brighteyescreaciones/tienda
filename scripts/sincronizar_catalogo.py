#!/usr/bin/env python3
"""Sincroniza solo el catálogo público desde Apps Script a GitHub Pages.
No necesita claves ni accede al panel privado de BrightEyes Studio.
"""
from __future__ import annotations
import datetime as dt
import json
import pathlib
import random
import re
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = ('https://script.google.com/macros/s/'
            'AKfycbzByfq4D8cw939wRIzQQRzsY3FNP1WjhaPpxJwsu_LG7aNa8OcuEb2Ty8LFLpPUV5N1/exec')
CALLBACK = 'beCatalogReceiver'
TARGET = pathlib.Path('catalogo.json')
PRODUCT_KEYS = ('activo','id','nombre','descripcion','categoria','precio_base','formato_archivo',
                'tamano_inicial','imagenes_inicial','etiqueta','imagen_url',
                *(f'imagen_url_{i}' for i in range(2, 11)))
PRICE_KEYS = ('producto_id','tamano','imagenes','precio')


def read_catalog():
    url = f'{ENDPOINT}?callback={CALLBACK}&t={int(time.time())}-{random.randint(1, 99999)}'
    req = urllib.request.Request(url,headers={'User-Agent':'BrightEyesCatalogSync/1.0'})
    with urllib.request.urlopen(req,timeout=28) as response:
        text = response.read(3_000_000).decode('utf-8-sig').strip()
    m = re.fullmatch(r'beCatalogReceiver\((.*)\);?',text,re.DOTALL)
    if m is None:
        raise ValueError('Respuesta inesperada de Google Apps Script')
    payload = json.loads(m.group(1))
    if not isinstance(payload,dict):
        raise ValueError('Datos no válidos')
    products = payload.get('productos')
    prices = payload.get('precios')
    if not isinstance(products,list) or not isinstance(prices,list):
        raise ValueError('Faltan las tablas Productos o Precios')
    active = [row for row in products if isinstance(row,dict) and str(row.get('activo','')).strip().upper()=='SI']
    if not active:
        raise ValueError('No hay productos activos; no se reemplazará la copia')
    ids = {str(row.get('id','')).strip() for row in active}
    if '' in ids:
        raise ValueError('Existe un producto sin código')
    if len(ids)!=len(active):
        raise ValueError('Existen identificadores duplicados')
    public_products = [{key:row.get(key,'') for key in PRODUCT_KEYS} for row in active]
    public_prices = [{key:row.get(key,'') for key in PRICE_KEYS}
                     for row in prices if isinstance(row,dict) and str(row.get('producto_id','')).strip() in ids]
    return {'actualizado':dt.datetime.now(dt.timezone.utc).isoformat(),
            'productos':public_products, 'precios':public_prices}


def main():
    last_error=None
    for attempt in range(3):
        try:
            data=read_catalog()
            # Keep the old valid file if the new response is empty or corrupted.
            TARGET.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
            print(f"Sincronizado: {len(data['productos'])} productos, {len(data['precios'])} precios")
            return 0
        except (OSError,UnicodeError,ValueError,urllib.error.URLError) as exc:
            last_error=exc
            print(f'Intento {attempt+1}/3: {exc}',file=sys.stderr)
            if attempt<2:time.sleep(4*(attempt+1))
    # Do not publish a new build with stale catalog when the Google service is down.
    print(f'El catálogo anterior sigue intacto. Error: {last_error}',file=sys.stderr)
    return 1


if __name__=='__main__':
    raise SystemExit(main())

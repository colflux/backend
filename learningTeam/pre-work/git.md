# Configurar llave SSH en GitHub

Sigue estos pasos en la terminal:

1. Genera una llave SSH:
```bash
ssh-keygen -t ed25519 -C "tu_email@example.com"
```

2. Presiona Enter para aceptar la ubicación por defecto y, si quieres, escribe una frase de seguridad.

3. Inicia el agente SSH:
```bash
eval "$(ssh-agent -s)"
```

4. Agrega la llave al agente:
```bash
ssh-add ~/.ssh/id_ed25519
```

5. Muestra la llave pública para copiarla:
```bash
cat ~/.ssh/id_ed25519.pub
```

6. Copia el contenido que aparece y añádelo en GitHub:
- Ve a GitHub
- Entra en Settings
- Abre SSH and GPG keys
- Haz clic en New SSH key
- Pega la llave y guarda

7. Prueba la conexión:
```bash
ssh -T git@github.com
```

Si te pide confirmar, escribe:
```bash
yes
```

Si quieres, también puedes usar esta configuración para evitar que te pida la contraseña cada vez:
```bash
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

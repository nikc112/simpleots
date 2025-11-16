# SimpleOTS – Self-Hosted One-Time-Password Tool
Dieses Tool ist mit Hilfe von ChatGPT erstellt worden.

**SimpleOTS** ist ein selbst gehostetes Tool zum sicheren Teilen von **einmalig abrufbaren Passwoertern**.  
Ideal fuer Admins, IT-Support und Unternehmen, die Passwoerter **nicht per E-Mail, WhatsApp oder Teams** austauschen wollen.

Die Anwendung speichert Passwoerter **nie im Klartext**, sondern verschluesselt sie mit AES-256 (Fernet), basierend auf einem eigenen `MASTER_KEY`, den der Nutzer selbst festlegt.

---

## ✨ Features

- 🔐 Einmal abrufbare Passwoerter (One-Time-Secrets)
- 🔒 AES-256 Verschluesselung (ueber MASTER_KEY)
- 👤 Admin-Bereich mit Login & Timeout
- 🖼 Eigenes Firmenlogo uploadbar
- ♻️ Factory Reset (setzt alles zurueck)
- 🗃 Redis-Datenbank fuer robuste Speicherung
- 📱 Responsive Web-UI
- 🧩 Komplett per Docker Compose installierbar
- 🚀 Produktionstauglich (Gunicorn + Redis)

---

# 🐳 Installation (fuer Endnutzer)

## 1. Repository klonen

```bash
git clone https://github.com/nikc112/simpleots.git
cd simpleots
2. Beispiel-Konfiguration kopieren
bash
Code kopieren
cp docker-compose.example.yml docker-compose.yml
3. docker-compose.yml bearbeiten
Datei oeffnen:


nano docker-compose.yml
BASE_URL setzen

BASE_URL: "http://SERVER-IP-ODER-DOMAIN:7143"
Beispiele:

http://192.168.1.50:7143

https://ots.meinefirma.de (wenn Reverse Proxy genutzt)

MASTER_KEY setzen
Ein langer, zufaelliger Schluessel (mind. 32–64 Zeichen):


MASTER_KEY: "hier_einen_langen_random_key_eintragen"
Guten Key generieren:

openssl rand -base64 48

4. Starten

docker compose up -d


5. Zugriff im Browser

http://SERVER-IP:7143
Beim ersten Start erscheint automatisch die Seite:

Admin Passwort festlegen

Danach steht das Tool sofort zur Verfuegung.

🔧 Optional: HTTPS via Reverse Proxy
SimpleOTS selbst nutzt kein HTTPS.
Fuer produktive Nutzung wird ein Reverse Proxy wie NGINX, Traefik oder NPM empfohlen.

Beispiel (NGINX):

server {
    listen 443 ssl;
    server_name ots.meinefirma.de;

    ssl_certificate /etc/letsencrypt/live/ots/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ots/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:7143;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
🖼 Logo anpassen
Im Admin-Bereich kann ein eigenes logo.png hochgeladen werden.
Das Logo wird lokal gespeichert unter:


./data/logo.png
Wenn kein Logo gesetzt ist, wird das mitgelieferte Default-Logo aus static/logo.png verwendet.

♻️ Werkseinstellungen
Im Admin-Bereich gibt es einen Knopf:

Werkseinstellungen zuruecksetzen

Dieser loescht:

alle gespeicherten Passwoerter (Redis)

das Admin-Passwort

das Logo

die aktuelle Admin-Session

Danach startet die Ersteinrichtung erneut.

🔄 Update
Wenn eine neue Version veroeffentlicht wurde:


git pull
docker compose pull
docker compose up -d
🛠 Fehlerbehebung
„Internal Server Error“
Logs ansehen:


docker logs simpleots --tail 50

Admin-Passwort vergessen?

rm ./data/admin.json
docker compose restart

Kompletten Reset durchfuehren:

rm -rf data redis
docker compose down
docker compose up -d

📄 Lizenz
MIT License – frei nutzbar und modifizierbar.

❤️ Mitwirken
Pull Requests und Verbesserungen sind willkommen!

#!/usr/bin/env python3
"""Script pour corriger le MODEL_NAME dans .env"""

import os

env_file = ".env"
correct_model = "gemini-2.5-flash"

# Lire le fichier .env s'il existe
if os.path.exists(env_file):
    with open(env_file, "r") as f:
        lines = f.readlines()
    
    # Chercher et remplacer MODEL_NAME
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("MODEL_NAME="):
            new_lines.append(f"MODEL_NAME={correct_model}\n")
            updated = True
            print(f"MODEL_NAME mis à jour vers {correct_model}")
        else:
            new_lines.append(line)
    
    # Si MODEL_NAME n'était pas présent, l'ajouter
    if not updated:
        new_lines.append(f"\nMODEL_NAME={correct_model}\n")
        print(f"MODEL_NAME ajouté avec la valeur {correct_model}")
    
    # Écrire le fichier mis à jour
    with open(env_file, "w") as f:
        f.writelines(new_lines)
    
    print("Fichier .env mis à jour avec succès!")
else:
    # Créer un nouveau fichier .env
    with open(env_file, "w") as f:
        f.write("# Configuration MongoDB\n")
        f.write("MONGODB_URI=mongodb://localhost:27017\n")
        f.write("DB_NAME=lg_db\n")
        f.write("\n# Configuration Gemini\n")
        f.write("GOOGLE_API_KEY=\n")
        f.write(f"MODEL_NAME={correct_model}\n")
    print("Fichier .env créé avec la configuration par défaut")

print("\nMaintenant, relance l'application avec : uv run streamlit run app.py")

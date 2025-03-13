CREATE DATABASE crypto_consultas

USE crypto_consultas

CREATE TABLE consultas(
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pergunta VARCHAR(255),
    resposta TEXT,
    custo_chatgpt FLOAT,
    custo_coingecko FLOAT
)

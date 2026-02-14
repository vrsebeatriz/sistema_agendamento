# 💈 Sistema de Agendamento - API Barbearia

API REST desenvolvida em FastAPI para gerenciamento completo de agendamentos de uma barbearia.

O sistema permite:

- Cadastro de clientes e barbeiros
- Autenticação via JWT
- Gerenciamento de serviços
- Configuração de horário semanal
- Criação de bloqueios (feriados/compromissos)
- Criação e controle de agendamentos
- Geração automática de horários disponíveis
- Controle de status do atendimento

---

# 🏗 Arquitetura

A aplicação está organizada em:

app/
- models → entidades do banco
- routers → endpoints da API
- core → segurança e autenticação
- database → engine e sessão
- scripts → seed inicial

Banco de dados: PostgreSQL  
ORM: SQLModel  
Framework: FastAPI  

---

# 🔐 Autenticação

O sistema utiliza autenticação baseada em JWT (Bearer Token).

Fluxo:

1. Usuário realiza login
2. API retorna um access_token
3. Token deve ser enviado no header:

Authorization: Bearer {token}

---

# 👥 Perfis de Usuário

Existem dois tipos de usuário:

## client
- Pode visualizar serviços
- Pode visualizar horários disponíveis
- Pode criar agendamento
- Pode listar seus próprios agendamentos

## barber
- Pode criar e editar serviços
- Pode configurar horário semanal
- Pode criar bloqueios
- Pode visualizar agenda
- Pode gerenciar status de agendamentos

---

# ✂️ Serviços

Cada serviço contém:

- name
- duration_minutes
- price
- active
- barber_id

Serviços desativados não aparecem para clientes.

---

# 🕒 Horário de Funcionamento

O horário é configurado por dia da semana.

Campos:

- weekday (0 a 6)
- is_closed
- open_time
- close_time
- lunch_start (opcional)
- lunch_end (opcional)

O sistema considera:

- Dia fechado
- Horário de abertura e fechamento
- Intervalo de almoço (se configurado)

---

# 🚫 Bloqueios

Bloqueios são períodos específicos onde o barbeiro não está disponível.

Exemplos:
- Feriado
- Consulta médica
- Evento externo

Campos:
- start_time
- end_time
- reason

---

# 📅 Agendamentos

Estrutura do agendamento:

- client_id
- barber_id
- service_id
- appointment_time
- status
- created_at
- canceled_at
- canceled_by
- cancel_reason

Status possíveis:

- pending
- confirmed
- completed
- canceled
- no_show

---

# ⏳ Geração de Horários Disponíveis

O endpoint /appointments/available calcula dinamicamente os horários livres considerando:

- Horário semanal configurado
- Bloqueios cadastrados
- Agendamentos já existentes
- Duração do serviço
- Intervalos de almoço

O frontend não precisa realizar nenhuma lógica de conflito.

---

# 🛠 Como executar o projeto

Crie seu ambiente virtual: python -m venv venv

1. Ativar ambiente virtual
    .\venv\Scripts\Activate.ps1

2. Instale as dependências
    pip install -r requirements.txt

3. Rodar servidor
    uvicorn app.main:app --reload

3. Acessar documentação automática:
    http://localhost:8000/docs

⚠️ É necessário criar um banco PostgreSQL chamado "barbearia"

---

# 🚀 Futuras Evoluções

- Dashboard financeiro
- Integração com pagamento online
- Notificação por WhatsApp

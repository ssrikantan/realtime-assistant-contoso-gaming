import json
import random
import chainlit as cl
from datetime import datetime, timedelta
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from chainlit.logger import logger
import pyodbc
from config import DefaultConfig
from atlassian import Jira

l_connection = None

def init_connections():
    global l_connection
    global l_jira
    try:
        l_connection = pyodbc.connect('Driver={ODBC Driver 18 for SQL Server};SERVER=' + 
                                      DefaultConfig.az_db_server + 
                                      ';DATABASE=' + DefaultConfig.az_db_database + 
                                      ';UID=' + DefaultConfig.az_db_username + 
                                      ';PWD=' + DefaultConfig.az_db_password)
        logger.info("Connected to the database....")
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")
        logger.error("Exiting the program....")
        exit(1)
    try:
        l_jira = Jira(
        url=DefaultConfig.attlassian_url,
        username=DefaultConfig.attlassian_user_name,
        password=DefaultConfig.attlassian_api_key)
        l_jira.myself()
        logger.info("Connected to Jira ticketing system....")
    except Exception as e:
        logger.error(f"Error connecting to Jira: {e}")
        logger.error("Exiting the program....")
        exit(1)

register_user_grievance_def = {
    "name": "register_user_grievance_def",
    "description": "register a grievance, or complaint or issue from the user in the Ticketing system",
    "parameters": {
        "type": "object",
        "properties": {
        "grievance_category": {
            "type": "string",
            "enum": [
                "wallet issues",
                "reward points issues",
                "gaming experience issues",
                "usage history issues",
                "other issues",
            ],
        },
            "grievance_description": {
                "type": "string",
                "description": "The detailed description of the grievance faced by the user",
            }
        },
        "required": ["grievance_category","grievance_description"],
    },
}

perform_search_based_qna = {  
    "name": "perform_search_based_qna",  
    "description": "Seek general assistance or register complaint with the AI assistant. This requires performing a search based QnA on the query provided by the user.",  
    "parameters": {  
        "type": "object",  
        "properties": {  
            "query": {  
                "type": "string",  
                "description": "The user query pertaining to gaming services"  
            }  
        },  
        "required": ["query"]  
    }  
}  

get_grievance_status_def = {
            "name": "get_grievance_status_def",
            "description": "fetch real time grievance status for a grievance id",
            "parameters": {
                "type": "object",
                "properties": {
                    "grievance_id": {
                        "type": "number",
                        "description": "The grievance id of the user registered in the Ticketing System",
                    }
                },
                "required": ["grievance_id"],
            },
        }

get_game_status_summary_def = {
    "name": "get_game_status_summary",
    "description": "retrieve the game status summary for a user based on the user name",
    "parameters": {
        "type": "object",
        "properties": {
            "user_name": {
                "type": "string",
                "description": "The user name of the user registered in the Gaming System",
            }
        },
        "required": ["user_name"],
    },
}


async def get_grievance_status_handler(grievance_id):
    response_message = ''
    response = ''
    JQL = 'project = ' + DefaultConfig.grievance_project_name +' AND id = ' +str(grievance_id)
    
    try:
        response_message = l_jira.jql(JQL)
        logger.info("Issue status retrieved successfully!")
        logger.info('grievance status response .. ', response_message)
        if response_message['issues']:
            response = "\n Here is the updated status of your grievance.\ngrievance_id : "+ response_message['issues'][0]['id']
            response += "\npriority : "+ response_message['issues'][0]['fields']['priority']['name']
            response += "\nstatus : "+ response_message['issues'][0]['fields']['status']['statusCategory']['key']
            response += "\ngrievance description : "+ response_message['issues'][0]['fields']['description']
            if response_message['issues'][0]['fields']['duedate']:
                response += "\ndue date : " + response_message['issues'][0]['fields']['duedate']
            else:
                response += "\ndue date : not assigned by the system yet."
        else:
            response = 'sorry, we could not locate a grievance with this ID. Can you please verify your input again?'
    except Exception as e:
        logger.error(f"Error retrieving the grievance: {e.args[0]}")
        response = 'We had an issue retrieving your grievance status. Please check back in some time'

    # Send the markdown table as a Chainlit message
    # await cl.Message(content=f"{response}").send()
    return response

async def register_user_grievance_handler(grievance_category, grievance_description):
        response_message = ''
        try:
            # Define the issue details (project key, summary, description, and issue type)

            issue_details = {
                'project': {'key': DefaultConfig.grievance_project_key},
                'summary': grievance_category,
                'description': grievance_description,
                'issuetype': {'name': 'Task'}
            }

            # Create the issue
            response = l_jira.create_issue(fields=issue_details)
            response_message = 'We are sorry about the issue you are facing. We have registered a grievance with id '+response['id'] +' to track it to closure. Please quote that in your future communications with us'
            logger.info("Issue created successfully!")
        except Exception as e:
            logger.error(f"Error registering the grievance issue: {e.args[0]}")
            response_message = 'We had an issue registering your grievance. Please check back in some time'

        # Send the markdown table as a Chainlit message
        # await cl.Message(content=f"{response_message}").send()
        return response_message

async def perform_search_based_qna_response_handler(query):
    logger.info("calling search to get context for the response ....")
    credential = AzureKeyCredential(DefaultConfig.ai_search_key)
    client = SearchClient(endpoint=DefaultConfig.ai_search_url, index_name=DefaultConfig.ai_index_name, credential=credential)
    results = list(
        client.search(
            search_text=query,
            query_type="semantic",
            semantic_configuration_name=DefaultConfig.ai_semantic_config,
        )
    )
    response_docs = ""
    counter = 0
    for result in results:
        logger.info(f"search result............\n {result}")
        response_docs += " --- Document context start ---"+ result['content'] + "\n ---End of Document ---\n"
        counter += 1
        if counter == 2:
            break
    logger.info(f"search results from the SOW Archives are : \n {response_docs}")
    logger.info("***********  calling LLM now ....***************")
    return response_docs


async def get_game_status_summary_handler(user_name):
        response_message = ''
        cursor = None
        logger.info(f"calling the database to fetch game status summary for {user_name}")
        try:
            cursor = l_connection.cursor()
            query = 'SELECT user_name, game_type, COUNT(*) AS games_played, SUM(entry_fee) AS total_entry_fee, SUM(points_earned) AS total_points_earned, SUM(cash_won) AS total_cash_won FROM Gaming_Transaction_History AS gth WHERE user_name = ? GROUP BY user_name, game_type ORDER BY user_name, game_type;'
            cursor.execute(query, user_name)
            logger.info('executed query successfully')
            response_message += '' 
            # add the column name corresponding to each value in the row to the response message first
            column_names = [description[0] for description in cursor.description]
            
            table_rows = ""
            # Build markdown table
            table_header = "| Game Type | Games Played | Total Entry Fee | Total Points Earned | Total Cash Won |\n"
            table_separator = "| --- | --- | --- | --- | --- |\n"
            table_rows = ""

            for row in cursor:
                table_rows += f"| {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |\n"

            markdown_table = table_header + table_separator + table_rows

            # Send the markdown table as a Chainlit message
            # await cl.Message(content=f"Here is your game status summary:\n\n{markdown_table}").send()
        except Exception as e:
            logger.error(f"Error in database query execution: {e}")
            response_message = 'We had an issue retrieving your grievance status. Please check back in some time'
        return markdown_table
 
# Tools list
tools = [
    (get_game_status_summary_def, get_game_status_summary_handler),
    (perform_search_based_qna,perform_search_based_qna_response_handler),
    (register_user_grievance_def, register_user_grievance_handler),
    (get_grievance_status_def, get_grievance_status_handler)
]
#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

class DefaultConfig:
    """ Bot Configuration """
    # API key either from Azure OpenAI, or OpenAI
    az_openai_key = ""
    
    # These apply only when using Azure OpenAI
    az_open_ai_endpoint_name = "aoai-gpt4-001"
    az_openai_api_version = "2024-10-01-preview"
    deployment_name = "gpt-4o" 

    attlassian_api_key = ''
    attlassian_user_name = '<>@hotmail.com'
    attlassian_url = 'https://<>.atlassian.net/'
    
    ai_search_url = "https://<>.search.windows.net"
    ai_search_key = ""
    ai_index_name = "contoso-gaming-index"
    ai_semantic_config = "contoso-gaming-config"

    # The following is for the demo to Gameskraft
    grievance_project_key = 'CN'
    grievance_type = 'Task'
    grievance_project_name = 'ContosoGamingSupport'


    ai_assistant_organization_name = "Contoso Gaming Inc."


    az_db_server = "<>.database.windows.net"
    az_db_database = "cdcsampledb"
    az_db_username = ""
    az_db_password = ""

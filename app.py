import os
import asyncio
from openai import AsyncAzureOpenAI

import chainlit as cl
from uuid import uuid4
from chainlit.logger import logger

from realtime import RealtimeClient
from realtime.tools import tools, init_connections

# # Variable to store the message ID for updates
# message_id = None
# # Initialize a variable to store the complete transcript
# complete_transcript = ""

async def setup_openai_realtime(system_prompt: str):
    """Instantiate and configure the OpenAI Realtime Client"""
    openai_realtime = RealtimeClient(system_prompt = system_prompt)
    cl.user_session.set("track_id", str(uuid4()))
    
    ## added these to update the chat message with streaming text
    # cl.user_session.set("message_id", None)
    # cl.user_session.set("complete_transcript", "")
    
    async def handle_conversation_updated(event):
        item = event.get("item")
        # print("event",event)
        delta = event.get("delta")
        role = item.get("role")
        """Currently used to stream audio back to the client."""
        if delta:
            # Only one of the following will be populated for any given event
            if 'audio' in delta:
                audio = delta['audio']  # Int16Array, audio added
                await cl.context.emitter.send_audio_chunk(cl.OutputAudioChunk(mimeType="pcm16", data=audio, track=cl.user_session.get("track_id")))
            if 'transcript' in delta:
                transcript = delta['transcript']  # string, transcript added
                if role == 'user':
                    await cl.Message(content=transcript, author="user", type="user_message").send()
            if 'arguments' in delta:
                arguments = delta['arguments']  # string, function arguments added
                pass
            
    async def handle_item_completed(item):
        """Used to populate the chat context with transcription once an item is completed."""
        # print(item)
        # try:
        #     response_text = ['item']['content'][0]['transcript']
        #     if response_text is not None and response_text != "":
        #         # print("response_text",response_text)
        #         await cl.Message(content=response_text).send()

        # except Exception as e:
        #     pass

    async def handle_audio_transcript_completed(event):
        """Used to populate the chat context with transcription once an audio transcript is completed."""
        # print("AUDIO TRANSCRIPT COMPLETED...")
        # print(event)
        response_text = event.get("transcript")
        try:

            if response_text is not None and response_text != "":
                # print("response_text",response_text)
                await cl.Message(content=response_text).send()

        except Exception as e:
            pass
    
    async def handle_conversation_interrupt(event):
        """Used to cancel the client previous audio playback."""
        cl.user_session.set("track_id", str(uuid4()))
        # cl.user_session.set("message_id", None)
        # cl.user_session.set("complete_transcript", "")
        await cl.context.emitter.send_audio_interrupt()
        
    async def handle_error(event):
        logger.error(event)
        
    openai_realtime.on('response.audio_transcript.done', handle_audio_transcript_completed)
    openai_realtime.on('conversation.updated', handle_conversation_updated)
    openai_realtime.on('conversation.item.completed', handle_item_completed)
    openai_realtime.on('conversation.interrupted', handle_conversation_interrupt)
    openai_realtime.on('error', handle_error)

    cl.user_session.set("openai_realtime", openai_realtime)
    coros = [openai_realtime.add_tool(tool_def, tool_handler) for tool_def, tool_handler in tools]
    await asyncio.gather(*coros)
    

system_prompt = """Provide helpful and empathetic support responses to customer inquiries for Contoso in English language, addressing their requests, concerns, or feedback professionally.

Maintain a friendly and service-oriented tone throughout the interaction to ensure a positive customer experience.

# Steps

1. **Identify the Issue:** Carefully read the customer's inquiry to understand the problem or question they are presenting.
2. **Gather Relevant Information:** Check for any additional data needed, such as order numbers or account details, while ensuring the privacy and security of the customer's information.
3. **Formulate a Response:** Develop a solution or informative response based on the understanding of the issue. The response should be clear, concise, and address all parts of the customer's concern.
4. **Offer Further Assistance:** Invite the customer to reach out again if they need more help or have additional questions.
5. **Close Politely:** End the conversation with a polite closing statement that reinforces the service commitment of Contoso.
6. **Do not speculate** When the provided information is not sufficient to address the customer's inquiry, avoid making assumptions or guesses. Instead, seek additional information to determine if you can respond factually. As a last resort,say you do not know. But always be factual in your responses.

# Output Format

Provide a clear and concise paragraph addressing the customer's inquiry, including:
- Acknowledgment of their concern
- Suggested solution or response
- Offer for further assistance
- Polite closing

# Notes
- Greet user with Welcome to Contoso For the first time only
- Ensure all customer data is handled according to relevant privacy and data protection laws and Contoso's privacy policy.
- In cases of high sensitivity or complexity, escalate the issue to a human customer support agent.
- Keep responses within a reasonable length to ensure they are easy to read and understand."""

@cl.on_chat_start
async def start():
    await cl.Message(
        content="Hi, Welcome! You are now connected to Contoso Gaming Services' AI Assistant. Press `P` to talk to her!"
    ).send()
    await setup_openai_realtime(system_prompt=system_prompt + "\n\n user_name: Srikantan")
    init_connections()
    # await setup_openai_realtime(system_prompt=system_prompt)

@cl.on_message
async def on_message(message: cl.Message):
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime and openai_realtime.is_connected():
        await openai_realtime.update_session(temperature=0.3, input_audio_transcription=True)
        await openai_realtime.send_user_message_content([{ "type": 'input_text', "text": message.content}])
    else:
        await cl.Message(content="Please activate voice mode before sending messages!").send()

@cl.on_audio_start
async def on_audio_start():
    try:
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
        # TODO: might want to recreate items to restore context
        # openai_realtime.create_conversation_item(item)
        await openai_realtime.connect()
        logger.info("Connected to OpenAI realtime")
        return True
    except Exception as e:
        await cl.ErrorMessage(content=f"Failed to connect to OpenAI realtime: {e}").send()
        return False

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime:            
        if openai_realtime.is_connected():
            await openai_realtime.append_input_audio(chunk.data)
        else:
            logger.info("RealtimeClient is not connected")


@cl.on_audio_end
@cl.on_chat_end
@cl.on_stop
async def on_end():
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime and openai_realtime.is_connected():
        logger.info("RealtimeClient session ended")
        await openai_realtime.disconnect()
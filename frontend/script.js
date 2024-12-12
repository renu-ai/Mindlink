let sessionId = null;
let currentState = "chat"; //default state=="chat"
let lastPuzzle = null; //track the last puzzle provided by the assistant

//function to send chat messages
async function sendChatMessage() {
    const userInput = document.getElementById("userInput").value;
    const chatBox = document.getElementById("chatBox");

    //display user message
    const userMessage = document.createElement("div");
    userMessage.className = "message user";
    userMessage.textContent = userInput;
    chatBox.appendChild(userMessage);

    //clear input field
    document.getElementById("userInput").value = "";

    try {
        //send chat message to the backend
        const payload = {
            input_text: userInput,
            session_id: sessionId,
            current_state: currentState, //include current state
        };

        const response = await fetch("http://127.0.0.1:8000/chat/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        //update session ID if it's the first request
        if (!sessionId) sessionId = data.session_id;

        const assistantMessage = data.response || data.error;

        //display assistant response
        const botMessage = document.createElement("div");
        botMessage.className = "message assistant";
        botMessage.textContent = assistantMessage;
        chatBox.appendChild(botMessage);

        //scroll chatbox to the bottom
        chatBox.scrollTop = chatBox.scrollHeight;
    } catch (error) {
        console.error("Error communicating with chat backend:", error);
    }
}

//function to send puzzle messages
async function sendPuzzleMessage(userInput = "") {
    const chatBox = document.getElementById("chatBox");

    //display user message if provided
    if (userInput) {
        const userMessage = document.createElement("div");
        userMessage.className = "message user";
        userMessage.textContent = userInput;
        chatBox.appendChild(userMessage);
    }

    try {
        //determine whether the user input is a new request or an answer to a puzzle
        const isAnswer = lastPuzzle !== null && userInput.trim() !== "";

        // Prepare payload
        const payload = {
            input_text: userInput,
            session_id: sessionId || null,
            is_answer: isAnswer, //flag to indicate answer
            current_state: currentState, //explicitly send the current state
        };

        //send request to the backend
        const response = await fetch("http://127.0.0.1:8000/generate_puzzle/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        //update session ID if it's the first request
        if (!sessionId && data.session_id) {
            sessionId = data.session_id;
        }

        //handle the response
        const assistantMessage = data.response || data.error;

        //if this is a new puzzle, save it in `lastPuzzle`
        if (!isAnswer) {
            lastPuzzle = assistantMessage; //save the puzzle for validation
            currentState = "puzzle"; //explicitly set state to "puzzle"
        }

        //display assistant response
        const botMessage = document.createElement("div");
        botMessage.className = "message assistant";
        botMessage.textContent = assistantMessage;
        chatBox.appendChild(botMessage);

        //scroll chatbox to the bottom
        chatBox.scrollTop = chatBox.scrollHeight;
    } catch (error) {
        console.error("Error communicating with puzzle backend:", error);
        const errorMessage = document.createElement("div");
        errorMessage.className = "message assistant";
        errorMessage.textContent = "An error occurred while generating the puzzle. Please try again.";
        chatBox.appendChild(errorMessage);
    }
}

//voice input processing
async function handleVoiceInput() {
    const voiceFile = document.getElementById("voiceInput").files[0];
    if (!voiceFile) {
        alert("Please upload a voice file.");
        return;
    }

    try {
        const formData = new FormData();
        formData.append("file", voiceFile);
        formData.append("session_id", sessionId); //include session ID

        const response = await fetch("http://127.0.0.1:8000/process_voice/", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();
        const voiceText = data.text || data.error;

        //display extracted text in the chatbox
        const botMessage = document.createElement("div");
        botMessage.className = "message assistant";
        botMessage.textContent = `Extracted from voice: ${voiceText}`;
        document.getElementById("chatBox").appendChild(botMessage);
    } catch (error) {
        console.error("Error processing voice input:", error);
    }
}

//image input processing
async function handleImageInput() {
    const imageFile = document.getElementById("imageInput").files[0];
    if (!imageFile) {
        alert("Please upload an image file.");
        return;
    }

    try {
        const formData = new FormData();
        formData.append("file", imageFile);
        formData.append("session_id", sessionId); //include session ID

        const response = await fetch("http://127.0.0.1:8000/process_image/", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();
        const message = data.message || data.error;

        //display image processing result in the chatbox
        const botMessage = document.createElement("div");
        botMessage.className = "message assistant";
        botMessage.textContent = `Image result: ${message}`;
        document.getElementById("chatBox").appendChild(botMessage);
    } catch (error) {
        console.error("Error processing image input:", error);
    }
}

//event listeners
document.getElementById("sendButton").addEventListener("click", sendChatMessage);
document.getElementById("puzzleButton").addEventListener("click", () => {
    currentState = "puzzle"; 
    sendPuzzleMessage("Let's start a puzzle!");
});
document.getElementById("voiceButton").addEventListener("click", () => document.getElementById("voiceInput").click());
document.getElementById("imageButton").addEventListener("click", () => document.getElementById("imageInput").click());
document.getElementById("voiceInput").addEventListener("change", handleVoiceInput);
document.getElementById("imageInput").addEventListener("change", handleImageInput);

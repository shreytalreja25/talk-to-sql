import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import DownloadButtons from './components/DownloadButtons';
import 'bootstrap/dist/css/bootstrap.min.css';

const App = () => {
    const [pastChats, setPastChats] = useState([]);
    const [queryResults, setQueryResults] = useState([]);

    const handleNewChat = (query) => {
        setPastChats([...pastChats, { query }]);
    };

    return (
        <div className="container-fluid d-flex">
            <div className="main-content p-4">
                <ChatInterface onNewChat={handleNewChat} />
            </div>
        </div>
    );
};

export default App;

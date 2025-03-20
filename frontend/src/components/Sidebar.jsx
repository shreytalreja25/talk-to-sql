import React from 'react';
import { List, MessageSquare } from 'lucide-react';

const Sidebar = ({ pastChats, onSelectChat }) => {
    return (
        <div className="sidebar border-end p-3">
            <h4><List size={20} className="me-2" /> Past Chats</h4>
            <ul className="list-group">
                {pastChats.map((chat, index) => (
                    <li key={index} className="list-group-item" onClick={() => onSelectChat(chat)}>
                        <MessageSquare size={16} className="me-2" />
                        {chat.query}
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default Sidebar;

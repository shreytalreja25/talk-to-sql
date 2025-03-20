import React, { useState } from "react";
import axios from "axios";
import { Download, Send } from "lucide-react";
import { Button, Table } from "react-bootstrap";

const ChatInterface = () => {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [result, setResult] = useState([]);

  const handleSend = async () => {
    if (!query.trim()) return;

    const newMessages = [...messages, { role: "user", content: query }];
    setMessages(newMessages);

    try {
      const response = await axios.get(`http://127.0.0.1:8000/execute-query?question=${encodeURIComponent(query)}`);
      setMessages([...newMessages, { role: "bot", content: response.data }]);
      setResult(response.data.result);
    } catch (error) {
      setMessages([...newMessages, { role: "bot", content: "Error fetching response." }]);
    }

    setQuery("");
  };

  const downloadCSV = () => {
    if (!result.length) return;
    const csvData = [Object.keys(result[0]).join(",")].concat(result.map(row => Object.values(row).join(","))).join("\n");
    const blob = new Blob([csvData], { type: "text/csv" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "query_results.csv";
    link.click();
  };

  const downloadExcel = () => {
    if (!result.length) return;
    import("xlsx").then(xlsx => {
      const worksheet = xlsx.utils.json_to_sheet(result);
      const workbook = xlsx.utils.book_new();
      xlsx.utils.book_append_sheet(workbook, worksheet, "Results");
      xlsx.writeFile(workbook, "query_results.xlsx");
    });
  };

  return (
    <div className="container mt-4">
      <div className="row">
        {/* Sidebar for past chats */}
        <div className="col-md-3 border-end">
          <h5>📜 Past Chats</h5>
          <ul className="list-group">
            {messages.filter(msg => msg.role === "user").map((msg, index) => (
              <li key={index} className="list-group-item">
                📝 {msg.content}
              </li>
            ))}
          </ul>
        </div>

        {/* Chat Interface */}
        <div className="col-md-9">
          <div className="chat-container border p-3" style={{ maxHeight: "400px", overflowY: "auto" }}>
            {messages.map((msg, index) => (
              <p key={index} className={msg.role === "user" ? "fw-bold" : "text-muted"}>
                <strong>{msg.role === "user" ? "User:" : "Bot:"} </strong> {msg.role === "bot" && Array.isArray(msg.content.result) ? (
                  <Table striped bordered hover responsive>
                    <thead>
                      <tr>
                        {Object.keys(msg.content.result[0]).map((col, i) => <th key={i}>{col}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {msg.content.result.map((row, i) => (
                        <tr key={i}>
                          {Object.values(row).map((val, j) => <td key={j}>{val}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                ) : msg.content}
              </p>
            ))}
          </div>

          {/* Input Field and Buttons */}
          <div className="mt-3 d-flex">
            <input
              type="text"
              className="form-control"
              placeholder="Type your question..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyPress={e => e.key === "Enter" && handleSend()}
            />
            <Button variant="primary" className="ms-2" onClick={handleSend}>
              <Send size={20} />
            </Button>
          </div>

          {/* Download Buttons */}
          <div className="mt-3">
            <Button variant="outline-secondary" onClick={downloadCSV} className="me-2">
              <Download size={18} /> Download CSV
            </Button>
            <Button variant="success" onClick={downloadExcel}>
              <Download size={18} /> Download Excel
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;

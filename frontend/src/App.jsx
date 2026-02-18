import { useState } from 'react'
import { useEffect } from "react";

import './App.css'


export default function App() {

  useEffect(() => {
    fetch("http://127.0.0.1:8000/health")
      .then((r) => r.json())
      .then((data) => console.log("backend health:", data))
      .catch((e) => console.error("backend error:", e));
  }, []);

  return (
    <>
      <h1>Frontend</h1>
    </>
  )
}

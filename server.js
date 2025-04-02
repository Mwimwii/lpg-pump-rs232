const express = require("express");
const { PrismaClient } = require("@prisma/client");

const prisma = new PrismaClient();
const app = express();

app.use(express.json());

// Store transaction
app.post("/transactions", async (req, res) => {
  try {
    const transaction = await prisma.transaction.create({
      data: req.body,
    });
    res.json(transaction);
  } catch (error) {
    res.status(500).json({ error: "Error saving transaction" });
  }
});

// Fetch all transactions
app.get("/transactions", async (req, res) => {
  const transactions = await prisma.transaction.findMany();
  res.json(transactions);
});

app.listen(3000, () => console.log("Server running on port 3000"));

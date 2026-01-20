import { DateTime, Str, Num, Bool } from "chanfana";
import type { Context } from "hono";
import { z } from "zod";

interface Env {
  DATABASE_URL: string;
}

export type AppContext = Context<{ Bindings: Env }>;

export const Task = z.object({
	name: Str({ example: "lorem" }),
	slug: Str(),
	description: Str({ required: false }),
	completed: z.boolean().default(false),
	due_date: DateTime(),
});


export const TransactionData = z.object({
  scaleId: Num({ description: "Identifier for the scale", example: 1 }),
  operatorId: Num({ description: "Identifier for the operator", example: 101 }),
  initialMass: Num({ description: "Initial mass reading", example: 50.5 }),
  tareMass: Num({ description: "Tare mass reading", example: 5.2 }),
  fillMass: Num({ description: "Fill mass reading", example: 40.3 }),
  lastMeasurement: Num({ description: "Last measured mass", example: 45.5 }),
  fillSequence: Num({ description: "Sequence number of the fill operation", example: 1 }),
  statusCode: Num({ description: "Status code for the transaction", example: 200 }),
});

export const Transaction = TransactionData.extend({ 
  id: Num({ description: "Unique identifier for the transaction (auto-generated)" }),
  createdAt: DateTime({ description: "Timestamp of when the transaction was created (auto-generated)" }),
});
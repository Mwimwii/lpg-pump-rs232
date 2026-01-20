// src/endpoints/transactionCreate.ts
import { OpenAPIRoute, Bool } from "chanfana";
import { z } from "zod";
import { type AppContext, Transaction, TransactionData } from "../types"; // Ensure these are correctly defined in types.ts
import { getPrismaClient } from "../lib/prisma"; // Ensure this utility exists and is correctly set up

export class TransactionCreate extends OpenAPIRoute {
	// Define the OpenAPI schema for this endpoint
	schema = {
		tags: ["Transactions"], // Tag for grouping in OpenAPI UI
		summary: "Create a new Transaction", // Summary of the endpoint
		request: {
			body: { // Define the expected request body
				content: {
					"application/json": {
						schema: TransactionData, // Use the TransactionData Zod schema for request body validation
					},
				},
			},
		},
		responses: { // Define possible responses
			"200": { // Successful response
				description: "Returns the created transaction",
				content: {
					"application/json": {
						// Chanfana typically wraps the response in a standard structure
						schema: z.object({
							series: z.object({
								// Removed 'const: true'
								success: Bool({ description: "Indicates if the request was successful" }),
								result: z.object({
									transaction: Transaction, // The created transaction, conforming to the Transaction Zod schema
								}),
							}),
						}),
					},
				},
			},
			"400": { // Bad request (e.g., validation error)
				description: "Invalid request data",
				content: {
					"application/json": {
						schema: z.object({
							series: z.object({
								// Removed 'const: false'
								success: Bool({ description: "Indicates that the request failed due to invalid data" }),
								error: z.string().openapi({description: "Description of the validation error"}),
                                issues: z.array(z.object({ // Zod validation issues
                                    message: z.string()
                                })).optional().openapi({description: "Detailed validation issues"})
							}),
						}),
					},
				},
			},
			"500": { // Server error
				description: "Error saving transaction",
				content: {
					"application/json": {
						schema: z.object({
							series: z.object({
								// Removed 'const: false'
								success: Bool({ description: "Indicates that the request failed due to a server error" }),
								error: z.string().openapi({description: "Description of the server error"}),
							}),
						}),
					},
				},
			},
		},
	};

	// Handle the incoming request
	async handle(c: AppContext) {
		try {
			// Get validated data from the request body.
			// Chanfana automatically validates against `this.schema.request.body`
			// and throws an error if validation fails, which can be caught.
			const validatedData = await this.getValidatedData<typeof this.schema>();
			const transactionToCreate = validatedData.body;

			// Get the Prisma Client instance, passing the DATABASE_URL from environment variables
			const prisma = getPrismaClient(c.env.DATABASE_URL);

			// Create the new transaction in the database
			const newTransaction = await prisma.transaction.create({
				data: transactionToCreate, // `transactionToCreate` is type-safe and validated
			});

			// Return the created transaction. Chanfana will wrap this in the standard success response structure.
			// The 'success: true' part of the response is typically handled by chanfana's wrapping based on a 2xx status.
			return {
				transaction: newTransaction,
			};

		} catch (error: any) {
			// Log the error for debugging
			console.error("Error in TransactionCreate:", error);

			// Handle Zod validation errors specifically, which chanfana might throw
			if (error instanceof z.ZodError) {
				c.status(400); // Set HTTP status to Bad Request
				// Chanfana should build the response based on the 400 schema.
				// The 'success: false' part is implied or handled by chanfana's error wrapping.
				return {
					error: "Validation failed",
					issues: error.errors, // Provide Zod error details
				};
			}

			// Handle other errors (e.g., database errors)
			c.status(500); // Set HTTP status to Internal Server Error
			// Chanfana should build the response based on the 500 schema.
			// The 'success: false' part is implied or handled by chanfana's error wrapping.
			return {
				error: "An unexpected error occurred while saving the transaction.",
			};
		}
	}
}

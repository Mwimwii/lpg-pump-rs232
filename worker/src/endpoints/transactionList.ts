// src/endpoints/transactionList.ts
import { OpenAPIRoute, Bool, Num } from "chanfana"; // Import Num if you plan to add pagination/filtering
import { z } from "zod";
import { type AppContext, Transaction } from "../types"; // Ensure Transaction is correctly defined in types.ts
import { getPrismaClient } from "../lib/prisma"; // Ensure this utility exists

export class TransactionList extends OpenAPIRoute {
	// Define the OpenAPI schema for this endpoint
	schema = {
		tags: ["Transactions"], // Tag for grouping
		summary: "List all Transactions", // Summary
		// Example: Add request query parameters schema if you need pagination or filtering
		// request: {
		//   query: z.object({
		//     page: Num({ description: "Page number", default: 1, required: false, example: 1 }),
		//     limit: Num({ description: "Number of items per page", default: 10, required: false, example: 10 }),
		//     // Add other filters like operatorId, scaleId, date ranges etc.
		//     // operatorId: Num({ description: "Filter by operator ID", required: false }),
		//   }),
		// },
		responses: { // Define possible responses
			"200": { // Successful response
				description: "Returns a list of transactions",
				content: {
					"application/json": {
						// Chanfana typically wraps the response
						schema: z.object({
							series: z.object({
								// Removed 'const: true'
								success: Bool({ description: "Indicates if the request was successful" }),
								result: z.object({
									transactions: Transaction.array(), // An array of Transaction objects
									// Example: Add pagination metadata if implemented
									// totalItems: Num({description: "Total number of transactions"}),
									// totalPages: Num({description: "Total number of pages"}),
									// currentPage: Num({description: "Current page number"}),
								}),
							}),
						}),
					},
				},
			},
			"500": { // Server error
				description: "Error fetching transactions",
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
			// Example: Get validated query parameters if you defined them in the schema
			// const validatedQuery = await this.getValidatedData<typeof this.schema>();
			// const { page, limit /*, operatorId */ } = validatedQuery.query || {}; // Default to empty object if no query params

			// Get the Prisma Client instance
			const prisma = getPrismaClient(c.env.DATABASE_URL);

			// Fetch all transactions from the database
			// Example: Add pagination and filtering logic if query parameters are used
			// const skip = page && limit ? (page - 1) * limit : undefined;
			// const take = limit;
			// const whereClause = {};
			// if (operatorId) {
			//   whereClause.operatorId = operatorId;
			// }

			const allTransactions = await prisma.transaction.findMany({
				// where: whereClause, // Example
				// take: take,        // Example
				// skip: skip,         // Example
				orderBy: {
					createdAt: 'desc', // Optionally order results, e.g., by creation date
				}
			});

			// Example: Get total count for pagination
			// let totalItems;
			// if (page && limit) { // Only count if pagination is active
			//    totalItems = await prisma.transaction.count({ where: whereClause });
			// }
			// const totalPages = limit && totalItems ? Math.ceil(totalItems / limit) : undefined;


			// Return the list of transactions. Chanfana will wrap this.
			// The 'success: true' part of the response is typically handled by chanfana's wrapping based on a 2xx status.
			return {
				transactions: allTransactions,
				// Example: Include pagination metadata in the response
				// totalItems,
				// totalPages,
				// currentPage: page,
			};

		} catch (error: any) {
			// Log the error for debugging
			console.error("Error in TransactionList:", error);

			// Handle errors
			c.status(500); // Set HTTP status to Internal Server Error
			// Chanfana should build the response based on the 500 schema.
			// The 'success: false' part is implied or handled by chanfana's error wrapping.
			return {
				error: "An unexpected error occurred while fetching transactions.",
			};
		}
	}
}

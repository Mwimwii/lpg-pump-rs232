-- CreateTable
CREATE TABLE "Transaction" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "scaleId" INTEGER NOT NULL,
    "operatorId" INTEGER NOT NULL,
    "initialMass" REAL NOT NULL,
    "tareMass" REAL NOT NULL,
    "fillMass" REAL NOT NULL,
    "lastMeasurement" REAL NOT NULL,
    "fillSequence" INTEGER NOT NULL,
    "statusCode" INTEGER NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

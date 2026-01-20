/*
  Warnings:

  - You are about to alter the column `createdAt` on the `Transaction` table. The data in that column could be lost. The data in that column will be cast from `Unsupported("timestamp(3)")` to `DateTime`.
  - You are about to alter the column `fillMass` on the `Transaction` table. The data in that column could be lost. The data in that column will be cast from `Unsupported("double precision")` to `Float`.
  - You are about to alter the column `initialMass` on the `Transaction` table. The data in that column could be lost. The data in that column will be cast from `Unsupported("double precision")` to `Float`.
  - You are about to alter the column `lastMeasurement` on the `Transaction` table. The data in that column could be lost. The data in that column will be cast from `Unsupported("double precision")` to `Float`.
  - You are about to alter the column `tareMass` on the `Transaction` table. The data in that column could be lost. The data in that column will be cast from `Unsupported("double precision")` to `Float`.

*/
-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Transaction" (
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
INSERT INTO "new_Transaction" ("createdAt", "fillMass", "fillSequence", "id", "initialMass", "lastMeasurement", "operatorId", "scaleId", "statusCode", "tareMass") SELECT "createdAt", "fillMass", "fillSequence", "id", "initialMass", "lastMeasurement", "operatorId", "scaleId", "statusCode", "tareMass" FROM "Transaction";
DROP TABLE "Transaction";
ALTER TABLE "new_Transaction" RENAME TO "Transaction";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

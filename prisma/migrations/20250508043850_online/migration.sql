-- CreateTable
CREATE TABLE "Transaction" (
    "id" SERIAL NOT NULL,
    "scaleId" INTEGER NOT NULL,
    "operatorId" INTEGER NOT NULL,
    "initialMass" DOUBLE PRECISION NOT NULL,
    "tareMass" DOUBLE PRECISION NOT NULL,
    "fillMass" DOUBLE PRECISION NOT NULL,
    "lastMeasurement" DOUBLE PRECISION NOT NULL,
    "fillSequence" INTEGER NOT NULL,
    "statusCode" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Transaction_pkey" PRIMARY KEY ("id")
);

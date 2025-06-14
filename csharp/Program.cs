using System;
using System.IO.Ports; // Required for SerialPort
using System.Text;     // Required for Encoding
using System.Threading; // Required for Thread.Sleep and CancellationTokenSource
using System.IO;       // Required for Path and File logging
using System.Globalization; // For parsing float

namespace PayGasConsoleTester
{
    class Program
    {
        static SerialPort _serialPort;
        static bool _keepRunning = true;
        static StringBuilder _receivedDataBuffer = new StringBuilder();
        static string _defaultScaleID = "1"; // Default Scale ID for protocol commands

        static void Main(string[] args)
        {
            Console.WriteLine("--- .NET Comprehensive Pump/Scale Tester ---");
            Console.WriteLine("Allows sending various commands based on PayGas logic and ADCENG protocol.");
            
            // Graceful shutdown setup
            var cts = new CancellationTokenSource();
            Console.CancelKeyPress += (sender, e) =>
            {
                e.Cancel = true; 
                _keepRunning = false;
                cts.Cancel(); 
                Console.WriteLine("\nCtrl+C pressed. Exiting application...");
            };

            // --- Serial Port Configuration ---
            string portName = "COM8"; // IMPORTANT: Verify this is your correct COM port!
            int baudRate = 9600;      
            Parity parity = Parity.None;
            int dataBits = 8;
            StopBits stopBits = StopBits.One;

            _serialPort = new SerialPort();

            try
            {
                _serialPort.PortName = portName;
                _serialPort.BaudRate = baudRate;
                _serialPort.Parity = parity;
                _serialPort.DataBits = dataBits;
                _serialPort.StopBits = stopBits;
                _serialPort.DtrEnable = true; 
                _serialPort.RtsEnable = true; 
                _serialPort.ReadTimeout = 1000; 
                _serialPort.WriteTimeout = 500;
                // _serialPort.Handshake = Handshake.None; 

                _serialPort.DataReceived += new SerialDataReceivedEventHandler(Sp_DataReceived);

                _serialPort.Open();
                Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] Serial port {portName} opened successfully.");
                LogMessage($"Port {portName} opened (DTR={_serialPort.DtrEnable}, RTS={_serialPort.RtsEnable}, Handshake={_serialPort.Handshake})", "INFO");

                // --- Main Command Loop ---
                while (_keepRunning)
                {
                    DisplayMenu();
                    Console.Write("Enter command choice: ");
                    string choice = Console.ReadLine()?.Trim();

                    if (string.IsNullOrEmpty(choice)) continue;

                    if (choice.Equals("exit", StringComparison.OrdinalIgnoreCase))
                    {
                        _keepRunning = false;
                        break;
                    }
                    
                    ProcessCommandChoice(choice);

                    if (_keepRunning) // Only pause if not exiting
                    {
                        Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss}] Listening for responses for 5 seconds after command...");
                        Thread.Sleep(5000); // Wait for potential responses
                        Console.WriteLine(new string('-', 50));
                    }
                }
            }
            catch (Exception ex) // General catch for setup or unhandled issues
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] MAIN ERROR: {ex.Message}");
                LogMessage($"MAIN ERROR: {ex.Message}", "EXCEPTION");
                Console.ResetColor();
                Console.WriteLine("Press any key to exit.");
                Console.ReadKey();
            }
            finally
            {
                if (_serialPort != null && _serialPort.IsOpen)
                {
                    Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss}] Closing serial port {_serialPort.PortName}...");
                    _serialPort.DataReceived -= Sp_DataReceived;
                    _serialPort.Close();
                    LogMessage($"Port {_serialPort.PortName} closed.", "INFO");
                }
                Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] Application terminated.");
            }
        }

        static void DisplayMenu()
        {
            Console.WriteLine("\nAvailable Commands:");
            Console.WriteLine("--- PayGas Logic Commands ---");
            Console.WriteLine("  1. Send '^start*' (Initiate Operation)");
            Console.WriteLine("  2. Send '!{CurrentWeight},{FillWeight}*' (Set Fill Parameters)");
            Console.WriteLine("  3. Send '^abort*' (Abort Operation)");
            Console.WriteLine("  4. Send '?*' (Query Status - PayGas style)");
            Console.WriteLine("--- ADCENG Protocol Document Commands ---");
            Console.WriteLine("  5. Send '$ScaleID,1*' (Protocol Status Check)");
            Console.WriteLine("  6. Send '$ScaleID,2*' (Protocol Resend Last Transaction)");
            Console.WriteLine("  7. Send '$ScaleID,10*' (Protocol Request Firmware Version)");
            Console.WriteLine("  8. Send '$ScaleID,11*' (Protocol Request Max Rating)");
            Console.WriteLine("  config. Change Default Scale ID (current: " + _defaultScaleID + ")");
            Console.WriteLine("  exit. Exit application");
            Console.WriteLine(new string('-', 50));
        }

        static void ProcessCommandChoice(string choice)
        {
            string commandToSend = null;
            string scaleId = _defaultScaleID; // Use default or prompt

            try
            {
                switch (choice.ToLower())
                {
                    case "1":
                        commandToSend = "^start*";
                        Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] ACTION: If required, perform physical action (e.g., 'connect cylinder') after this command.");
                        break;
                    case "2":
                        Console.Write("Enter Current Weight (e.g., 03.50): ");
                        string currentWeightStr = Console.ReadLine();
                        Console.Write("Enter Fill Weight (e.g., 10.00): ");
                        string fillWeightStr = Console.ReadLine();
                        // Basic validation, can be improved
                        if (float.TryParse(currentWeightStr, NumberStyles.Any, CultureInfo.InvariantCulture, out _) &&
                            float.TryParse(fillWeightStr, NumberStyles.Any, CultureInfo.InvariantCulture, out _))
                        {
                            commandToSend = $"!{currentWeightStr},{fillWeightStr}*";
                        }
                        else
                        {
                            Console.WriteLine("Invalid weight format. Command not sent.");
                            return;
                        }
                        break;
                    case "3":
                        commandToSend = "^abort*";
                        break;
                    case "4":
                        commandToSend = "?*";
                        break;
                    case "5":
                        commandToSend = $"${scaleId},1*";
                        break;
                    case "6":
                        commandToSend = $"${scaleId},2*";
                        break;
                    case "7":
                        commandToSend = $"${scaleId},10*";
                        break;
                    case "8":
                        commandToSend = $"${scaleId},11*";
                        break;
                    case "config":
                        Console.Write($"Enter new Default Scale ID (current: {_defaultScaleID}): ");
                        string newId = Console.ReadLine()?.Trim();
                        if (!string.IsNullOrEmpty(newId) && int.TryParse(newId, out _)) // Basic check for numeric ID
                        {
                            _defaultScaleID = newId;
                            Console.WriteLine($"Default Scale ID set to: {_defaultScaleID}");
                        } else {
                            Console.WriteLine("Invalid Scale ID. Not changed.");
                        }
                        return; // No command to send
                    default:
                        Console.WriteLine("Invalid choice. Please try again.");
                        return; // No command to send
                }

                if (!string.IsNullOrEmpty(commandToSend))
                {
                    Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss}] Sending command: {commandToSend}");
                    _serialPort.Write(commandToSend);
                    LogMessage($"Sent: {commandToSend}", "TX");
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] Error sending command: {ex.Message}");
                LogMessage($"Error sending command '{commandToSend}': {ex.Message}", "EXCEPTION_TX");
                Console.ResetColor();
            }
        }

        private static void Sp_DataReceived(object sender, SerialDataReceivedEventArgs e)
        {
            SerialPort sp = (SerialPort)sender;
            try
            {
                int bytesToReadCount = sp.BytesToRead;
                if (bytesToReadCount > 0)
                {
                    byte[] receivedBytesBuffer = new byte[bytesToReadCount];
                    sp.Read(receivedBytesBuffer, 0, bytesToReadCount);
                    string rawData = Encoding.ASCII.GetString(receivedBytesBuffer);

                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss}] [DataReceived] RX ({bytesToReadCount} bytes): {rawData.Replace("\r", "\\r").Replace("\n", "\\n")}");
                    Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] [DataReceived] RX HEX: {BitConverter.ToString(receivedBytesBuffer).Replace("-", " ")}");
                    Console.ResetColor();
                    LogMessage($"Received Raw: {rawData} (HEX: {BitConverter.ToString(receivedBytesBuffer).Replace("-", " ")})", "RX_RAW");
                    
                    lock (_receivedDataBuffer)
                    {
                        _receivedDataBuffer.Append(rawData);
                    }
                    ProcessBufferedData();
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss}] [DataReceived] Error: {ex.Message}");
                LogMessage($"Error in DataReceived event: {ex.Message}", "EXCEPTION_RX");
                Console.ResetColor();
            }
        }

        private static void ProcessBufferedData()
        {
            string currentBufferContent;
            lock(_receivedDataBuffer)
            {
                currentBufferContent = _receivedDataBuffer.ToString();
            }

            char[] startChars = { '^', '$', '@', '?', '#', '!' }; 
            char endChar = '*';
            int searchStartIndex = 0; 

            while(true)
            {
                int actualMessageStartIndex = currentBufferContent.IndexOfAny(startChars, searchStartIndex);
                if (actualMessageStartIndex == -1) 
                {
                    if (searchStartIndex > 0 && searchStartIndex < currentBufferContent.Length) {
                        lock(_receivedDataBuffer) { _receivedDataBuffer.Remove(0, searchStartIndex); }
                    } else if (searchStartIndex >= currentBufferContent.Length) {
                         lock(_receivedDataBuffer) { _receivedDataBuffer.Clear(); }
                    }
                    break; 
                }

                int messageEndIndex = currentBufferContent.IndexOf(endChar, actualMessageStartIndex);
                if (messageEndIndex == -1) 
                {
                    if (actualMessageStartIndex > 0) {
                         lock(_receivedDataBuffer) { _receivedDataBuffer.Remove(0, actualMessageStartIndex); }
                    }
                    break; 
                }

                string completeMessage = currentBufferContent.Substring(actualMessageStartIndex, messageEndIndex - actualMessageStartIndex + 1);
                
                Console.ForegroundColor = ConsoleColor.Cyan;
                Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] [FrameProcessor] Parsed Message: {completeMessage}");
                Console.ResetColor();
                LogMessage($"Parsed Message: {completeMessage}", "FRAME");

                searchStartIndex = messageEndIndex + 1;
                if (searchStartIndex >= currentBufferContent.Length)
                {
                     lock(_receivedDataBuffer) { _receivedDataBuffer.Clear(); }
                    break; 
                }
            }
        }

        private static void LogMessage(string message, string type)
        {
            try
            {
                string logDirectory = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "dotnet_serial_logs");
                if (!Directory.Exists(logDirectory))
                {
                    Directory.CreateDirectory(logDirectory);
                }
                string logFileName = $"comprehensive_tester_log_{DateTime.Now:yyyy-MM-dd}.txt";
                string logFilePath = Path.Combine(logDirectory, logFileName);
                
                string logEntry = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] [{type}] {message}{Environment.NewLine}";
                File.AppendAllText(logFilePath, logEntry);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] Failed to write to log file: {ex.Message}");
            }
        }
    }
}

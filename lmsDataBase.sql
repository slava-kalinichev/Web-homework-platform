--
-- ���� ������������ � ������� SQLiteStudio v3.4.4 � �� ��� 10 15:35:52 2025
--
-- �������������� ��������� ������: System
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- �������: Accounts
CREATE TABLE IF NOT EXISTS Accounts (Login TEXT PRIMARY KEY, SecretPass TEXT NOT NULL, Status TEXT NOT NULL);

-- �������: AccountsRole
CREATE TABLE IF NOT EXISTS AccountsRole (AccRoleID INTEGER PRIMARY KEY, Login TEXT REFERENCES Accounts (Login), RoleID TEXT NOT NULL);

-- �������: Classes
CREATE TABLE IF NOT EXISTS Classes (ClassID INTEGER PRIMARY KEY, ClassTitle TEXT NOT NULL);

-- �������: ClassesInSchools
CREATE TABLE IF NOT EXISTS ClassesInSchools (CISID INTEGER PRIMARY KEY, SchoolID INTEGER REFERENCES Schools (SchoolID), ClassID INTEGER REFERENCES Classes (ClassID));

-- �������: ClassInvitations
CREATE TABLE IF NOT EXISTS ClassInvitations (
    InvitationID INTEGER PRIMARY KEY,
    ClassID INTEGER REFERENCES Classes (ClassID),
    StudentID INTEGER REFERENCES Students (StudentID),
    TeacherID INTEGER REFERENCES Teachers (TeacherID),
    Status TEXT NOT NULL, -- 'pending', 'accepted', 'rejected'
    CreatedAt INTEGER NOT NULL,
    UpdatedAt INTEGER);

-- �������: MyClasses
CREATE TABLE IF NOT EXISTS MyClasses (MCID INTEGER PRIMARY KEY, ClassID INTEGER REFERENCES Classes (ClassID), TeacherID INTEGER REFERENCES Teachers (TeacherID));

-- �������: Schools
CREATE TABLE IF NOT EXISTS Schools (SchoolID INTEGER PRIMARY KEY, SchoolName TEXT NOT NULL, SchoolCode TEXT NOT NULL);

-- �������: SolutionFiles
CREATE TABLE IF NOT EXISTS SolutionFiles (
    FileID INTEGER PRIMARY KEY,
    STID INTEGER REFERENCES StudentTasks (STID),
    FileName TEXT NOT NULL,
    FileData BLOB NOT NULL,
    MimeType TEXT NOT NULL
);

-- �������: StudentInClasses
CREATE TABLE IF NOT EXISTS StudentInClasses (SICID INTEGER PRIMARY KEY, ClassID INTEGER REFERENCES Classes (ClassID), StudentID INTEGER REFERENCES Students (StudentID));

-- �������: Students
CREATE TABLE IF NOT EXISTS Students (StudentID INTEGER PRIMARY KEY, Login TEXT REFERENCES Accounts (Login), LastName TEXT NOT NULL, FirstName TEXT NOT NULL, MiddleName TEXT NOT NULL);

-- �������: StudentTasks
CREATE TABLE IF NOT EXISTS StudentTasks (STID INTEGER PRIMARY KEY, StudentID INTEGER REFERENCES Students (StudentID), TaskID INTEGER REFERENCES Tasks (TaskID), Decision TEXT, Mark TEXT, Comment TEXT, Status TEXT NOT NULL, DispatchDT INTEGER);

-- �������: Subjects
CREATE TABLE IF NOT EXISTS Subjects (SubjectID INTEGER PRIMARY KEY, SubjectTitle TEXT NOT NULL UNIQUE);

-- �������: TaskFiles
CREATE TABLE IF NOT EXISTS TaskFiles (
    FileID INTEGER PRIMARY KEY,
    TaskID INTEGER REFERENCES Tasks (TaskID),
    FileName TEXT NOT NULL,
    FileData BLOB NOT NULL,
    MimeType TEXT NOT NULL
);

-- �������: Tasks
CREATE TABLE IF NOT EXISTS Tasks (TaskID INTEGER PRIMARY KEY, Date INTEGER NOT NULL, ClassID INTEGER REFERENCES Classes (ClassID), TeacherID INTEGER REFERENCES Teachers (TeacherID), SubjectID INTEGER REFERENCES Subjects (SubjectID), Topic TEXT NOT NULL, Text TEXT NOT NULL);

-- �������: Teachers
CREATE TABLE IF NOT EXISTS Teachers (TeacherID INTEGER PRIMARY KEY, Login TEXT REFERENCES Accounts (Login), LastName TEXT NOT NULL, FirstName TEXT NOT NULL, MiddleName TEXT NOT NULL);

-- �������: TeachersInSchools
CREATE TABLE IF NOT EXISTS TeachersInSchools (TISID INTEGER PRIMARY KEY, SchoolID INTEGER REFERENCES Schools (SchoolID), TeacherID INTEGER REFERENCES Teachers (TeacherID));

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;

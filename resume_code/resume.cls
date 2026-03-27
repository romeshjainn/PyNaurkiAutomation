\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume}[2025/01/01 Resume Class]

\LoadClass[9pt, letterpaper]{article}

\RequirePackage[
  top=0.24in, bottom=0.20in,
  left=0.45in, right=0.45in
]{geometry}
\RequirePackage{xcolor}
\RequirePackage{hyperref}
\RequirePackage[T1]{fontenc}
\RequirePackage[utf8]{inputenc}
\RequirePackage{titlesec}
\RequirePackage{enumitem}
\RequirePackage{parskip}
\RequirePackage[protrusion=true,expansion=false]{microtype}
\RequirePackage{tabularx}
\RequirePackage{array}
\RequirePackage{marvosym}
\RequirePackage{tikz}

%% Colours
\definecolor{accentblue}{HTML}{2B6CB0}
\definecolor{darkgray}{HTML}{2D2D2D}
\definecolor{medgray}{HTML}{555555}
\definecolor{rulegray}{HTML}{CCCCCC}

%% Hyperlinks
\hypersetup{
  colorlinks=true,
  urlcolor=accentblue,
  linkcolor=accentblue,
  pdfpagemode=UseNone
}

%% Font
\renewcommand{\familydefault}{\sfdefault}
\color{darkgray}
\pagestyle{empty}
\setlength{\parskip}{0pt}

%% Icon badges (LinkedIn / GitHub)
\newcommand{\iconbadge}[1]{%
  \tikz[baseline=-0.6ex]{%
    \node[fill=accentblue, text=white, rounded corners=1.5pt,
          inner xsep=2.2pt, inner ysep=1.0pt,
          font=\bfseries\fontsize{5.5pt}{5.5pt}\selectfont]{#1};%
  }%
}

%% Portfolio icon
\newcommand{\portfolioicon}{%
  \tikz[baseline=-0.6ex]{%
    \node[fill=accentblue, text=white, rounded corners=1.5pt,
          inner xsep=2.2pt, inner ysep=1.0pt,
          font=\bfseries\fontsize{5.5pt}{5.5pt}\selectfont]{PF};%
  }%
}

%% Section headings
\titleformat{\section}
  {\small\bfseries\color{darkgray}}
  {}{0em}{\MakeUppercase}
  [{\color{rulegray}\vspace{1pt}\hrule}\vspace{2pt}]
\titlespacing{\section}{0pt}{3pt}{1pt}

%% Bullet lists
\setlist[itemize]{
  leftmargin=1.1em,
  itemsep=0pt,
  topsep=0pt,
  parsep=0pt,
  partopsep=0pt,
  label=\textbullet
}

%% ================= HEADER =================
%% {Name}{Tagline}{Phone}{Email}{LinkedIn}{GitHub}{Portfolio}
\newcommand{\resumeheader}[7]{%
  \begin{center}
    {\LARGE\bfseries\color{accentblue} #1}\\[2pt]
    {\small\color{medgray} #2}\\[3pt]
    {\footnotesize
      \Mobilefone~#3 \enspace|\enspace
      \href{mailto:#4}{\Letter~#4} \enspace|\enspace
      \iconbadge{in}~\href{#5}{LinkedIn}
      \enspace|\enspace
      \iconbadge{gh}~\href{#6}{GitHub}
      \enspace|\enspace
      \portfolioicon~\href{#7}{Portfolio}
    }
  \end{center}
}

%% Company block header
\newcommand{\companyheader}[3]{%
  \noindent
  \href{#2}{\textbf{\color{accentblue}#1}} \hfill {\small\color{medgray}#3}
  \vspace{1pt}
}

%% Role entry
\newcommand{\roleentry}[2]{%
  \noindent
  \textit{\textbf{#1}} \hfill {\small\color{medgray}#2}
  \vspace{1pt}
}

%% Project entry
\newcommand{\projectentry}[2]{%
  \noindent
  \textbf{\color{accentblue}#1} {\small\color{medgray}| \textit{#2}}
  \vspace{1pt}
}

%% Education entry
\newcommand{\eduentry}[4]{%
  \noindent
  \textbf{\color{accentblue}#1} \textbar{} \textbf{#2}
  \hfill {\small\color{medgray}#3}\\
  {\small\color{medgray}#4}
}

%% Skill row
\newcommand{\skillrow}[2]{%
  \textbf{#1} & {\small #2} \\[0pt]
}

%% Continuation row
\newcommand{\skillcont}[1]{%
  & {\small #1} \\[0pt]
}
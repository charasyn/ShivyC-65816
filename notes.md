Issues:
- accessing data in another code section
    - not an issue, use far access
    - if accessing data in code section, ALWAYS use far access
- const near function pointer in sec1, accessed in sec2
    - 


Annotate all symbols with their segment.
Near access segments are `['DATA', 'BSS']`.
If data is in a near access segment, then generate near accesses, otherwise far accesses.
Each compilation unit will have its own `RODATA` and `CODE` segments. These will be named as follows: `<Segment>oCUo<Compilation Unit>`, where `<Segment>` is replaced with either `RODATA` or `CODE`, and `<Compilation Unit>` is replaced with the name of the compilation unit's root file (`__FILE__`, ignoring includes) put in uppercase with non-alphanumeric characters replaced with `x`.
Example: if you are compiling the file `test.c` then the code segment name will be `CODEoCUoTESTxC`. I really wish LD65 supported underscores.
`const` data is stored in the compilation unit's `RODATA` segment, otherwise data is stored in the `DATA` or `BSS` segment, as appropriate.
The keyword `__raw_segment__` can be used to override the segment used for a symbol.

Function: far vs. near goes after return type definition and before func. name


```
////////////////////////////////
//// Near vs. Far functions ////
// Far functions (default) - call with JSL, return with RTL
int far fnAddFar(int a, int b);
int fnAddFar2(int a, int b);
// Near functions - call with JSR, return with RTS
int near fnAddNear(int a, int b);

///////////////////////////////
//// Near vs. Far pointers ////
// Near pointer (default for data) - data accessed with absolute addressing
int near * ptrNear;
int * ptrNear2;
// Far pointer (default for function ptr.) - data accessed with
// direct page pointer dereference (LDA [$06] for example)
int far * ptrFar;

///////////////////////////////////////////
//// Near vs. Far functions + pointers ////
// Here's where stuff gets tricky.
// Near function returning far pointer.
int far * near fnWtf1(void);
// Far function returning near pointer.
int near * far fnWtf2(void);
int * fnWtf2b(void);
// Function pointer typedefs.
typedef int (*fpFarPointerFarFunction)(int,int);
typedef int near (near *fpNearPointerNearFunction)(int,int);
typedef int near (far  *fpFarPointerNearFunction)(int,int);
typedef int far  (near *fpNearPointerFarFunction)(int,int);
// Function pointer arrays.
fpFarPointerFarFunction const functionsAnywhere[] = { /* ... */ };
fpNearPointerNearFunction const functionsInYourSegment[] = {
    /* These functions must be in the same segment as the array,
     * otherwise the compiler will issue an error. */
};

__segment__("DATA7F") extern int bigarray1[1000];
extern __segment__("DATA7F") int bigarray2[1000];

// Unknown segment - will use far addressing
extern unsigned char const unkData[256];
extern void unkFunction(void);
// `near` function, but not in same segment!
// Calling this will issue a compiler error.
// In the future I guess we could generate JSL_RTS
// code, but it becomes a bit more complicated..
extern void near unkFunction2(void);

// Set the segment naming to a constant, instead of the
// default based on the compilation unit.
__segment_pushsuffix__("TEXTENGINE");
// After this, the default segment will no longer be 
// `CODEoCUoFILExC`, but instead `CODEoCUoTEXTENGINE`.
// This allows us to have code in different files be
// in the same segment.
extern void textFunc1(int);
// near function
extern void near textFunc2(int);

```

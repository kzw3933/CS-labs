#ifndef __VGA_H__
#define __VGA_H__

void append2screen(char *str, int color);
void clear_screen(void);

typedef struct cursorPos{
	unsigned char line;
	unsigned char col;
} cursorPos;

#endif

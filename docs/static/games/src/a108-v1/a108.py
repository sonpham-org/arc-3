"""a108 Guillotine Floor -- produce target rectangles through full recursive cuts."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FLOOR,REGION,CUT_H,CUT_V,SELECT,PIECE,FILLED,LEFTOVER,BAD=4,8,9,12,14,10,13,6,11,15
LEVELS=[
 {"name":"Horizontal Cut","seq":(1,)},{"name":"Vertical Cut","seq":(2,)},
 {"name":"Select Region","seq":(3,1)},{"name":"Recursive Tree","seq":(1,3,2,4,3)},
 {"name":"No Leftovers","seq":(2,3,1,4,3,2,4)},{"name":"Guillotine Floor","seq":(1,3,2,4,3,1,2,4,3,4)},
]
def advance(s,a):
 regions,cursor,pieces,filled,leftover,history,snapshot=s;r=list(regions)
 if a in (1,2):
  w,h=r[cursor]
  if a==1 and h>1:r[cursor]=(w,h//2);r.append((w,h-h//2))
  elif a==2 and w>1:r[cursor]=(w//2,h);r.append((w-w//2,h))
  pieces=(pieces+1)%8;history=(history+(a,))[-8:]
 elif a==3:cursor=(cursor+1)%len(r);history=(history+(3,))[-8:]
 elif a==4:filled=sum(int(w*h in (4,6,8)) for w,h in r);leftover=sum(w*h for w,h in r if w*h not in (4,6,8));history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(r),cursor,pieces,filled,leftover,history)
 return tuple(r),cursor,pieces,filled,leftover,history,snapshot
for x in LEVELS:
 s=(((8,6),),0,0,0,48,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FLOOR;x=y=8
  for i,(w,h) in enumerate(g.regions[:8]):
   ww=min(20,w*3);hh=min(16,h*3);f[y:y+hh,x:x+ww]=SELECT if i==g.cursor else REGION;f[y+2:y+hh-2,x+2:x+ww-2]=PIECE
   x+=ww+3
   if x>48:x=8;y+=19
  f[7:11,8:20]=CUT_H;f[7:11,22:34]=CUT_V;f[53:57,8:8+g.filled*7]=FILLED;f[57:60,8:8+min(10,g.leftover)*4]=LEFTOVER
  if g.bad:f[1:4,18:46]=BAD
  return f
class A108(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a108",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.regions,self.cursor,self.pieces,self.filled,self.leftover,self.history,self.snapshot=(((8,6),),0,0,0,48,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.regions,self.cursor,self.pieces,self.filled,self.leftover,self.history,self.snapshot=advance((self.regions,self.cursor,self.pieces,self.filled,self.leftover,self.history,self.snapshot),a)
  elif a==6:
   if (self.regions,self.cursor,self.pieces,self.filled,self.leftover,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

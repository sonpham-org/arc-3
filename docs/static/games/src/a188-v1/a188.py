"""a188 Synchronization Word -- design a cyclic delimiter with a unique alignment."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,STREAM,ZERO,ONE,DELIMITER,CURSOR,UNIQUE,ALIAS,PHASE=10,3,8,14,12,13,4,6,11
BAD=15
LEVELS=[
 {"name":"Flip Delimiter","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Shift Frame","seq":(3,1)},{"name":"Test Rotations","seq":(1,2,3,4,2)},
 {"name":"Break Alias","seq":(1,3,2,1,4,3,2)},{"name":"Synchronization Word","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def rotated(word,k):return ((word<<k)|(word>>(8-k)))&255 if k else word
def advance(s,a):
 word,cursor,phase,unique,aliases,history,snapshot=s
 if a==1:word^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:phase=(phase+1)%8;history=(history+(3,))[-8:]
 elif a==4:aliases=sum(int(rotated(word,k)==word) for k in range(1,8));unique=int(aliases==0);history=(history+(4,))[-8:]
 elif a==5:snapshot=(word,cursor,phase,unique,aliases,history)
 return word,cursor,phase,unique,aliases,history,snapshot
for q in LEVELS:
 s=(0b11010010,0,3,1,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=STREAM
  for row in range(3):
   for i in range(16):
    bit=(g.word>>((i+g.phase+row*3)%8))&1;x=7+i*3;y=13+row*13;f[y:y+8,x:x+2]=ONE if bit else ZERO
   start=7+((8-g.phase)%8)*3;f[y-3:y,start:start+24]=DELIMITER
  f[8:11,7+g.cursor*6:12+g.cursor*6]=CURSOR;f[54:58,8:28]=UNIQUE if g.unique else ALIAS;f[54:58,48:48+g.aliases*2]=ALIAS;f[7:10,52:58]=PHASE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A188(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a188",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.word,self.cursor,self.phase,self.unique,self.aliases,self.history,self.snapshot=(0b11010010,0,3,1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.word,self.cursor,self.phase,self.unique,self.aliases,self.history,self.snapshot=advance((self.word,self.cursor,self.phase,self.unique,self.aliases,self.history,self.snapshot),a)
  elif a==6:
   if (self.word,self.cursor,self.phase,self.unique,self.aliases,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""a092 Crease Memory -- train plastic hinges for an autonomous fold sequence."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,STUDIO,SHEET,GRID,FOLD,HINGE,CURSOR,SEQUENCE,SHAPE,BAD=4,8,9,10,12,14,13,11,6,15
LEVELS=[
 {"name":"Fold Once","seq":(1,)},{"name":"Select Crease","seq":(2,)},
 {"name":"Permanent Hinge","seq":(1,3,1)},{"name":"Unfold Sheet","seq":(1,2,1,3,4)},
 {"name":"Train Sequence","seq":(1,2,1,3,2,1,4)},{"name":"Crease Memory","seq":(1,3,2,1,4,2,1,3,4,1)},
]
def advance(s,a):
 strengths,folded,cursor,shape,sequence,history,snapshot=s;st=list(strengths);fo=list(folded)
 if a==1:st[cursor]=min(3,st[cursor]+1);fo[cursor]^=1;shape=(shape+cursor+1)%8;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:fo[cursor]=0;shape=(shape-cursor)%8;history=(history+(3,))[-8:]
 elif a==4:
  hinges=tuple(i for i,v in enumerate(st) if v>=2);sequence=(sequence+(hinges,))[-5:]
  for i in hinges:fo[i]^=1;shape=(shape+i+1)%8
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(st),tuple(fo),cursor,shape,sequence,history)
 return tuple(st),tuple(fo),cursor,shape,sequence,history,snapshot
for x in LEVELS:
 s=((0,0,0,0,0,0),(0,0,0,0,0,0),0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STUDIO;f[13:48,9:55]=SHEET
  for i,v in enumerate(g.strengths):
   if i<3:x=20+i*11;f[13:48,x:x+2]=HINGE if v>=2 else GRID
   else:y=20+(i-3)*10;f[y:y+2,9:55]=HINGE if v>=2 else GRID
  if g.cursor<3:x=20+g.cursor*11;f[8:12,x-2:x+5]=CURSOR
  else:y=20+(g.cursor-3)*10;f[y-2:y+5,56:59]=CURSOR
  f[51:56,8:8+g.shape*6]=SHAPE
  for i,_ in enumerate(g.sequence):f[7:10,38+i*4:41+i*4]=SEQUENCE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A092(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a092",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.strengths,self.folded,self.cursor,self.shape,self.sequence,self.history,self.snapshot=((0,0,0,0,0,0),(0,0,0,0,0,0),0,0,(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.strengths,self.folded,self.cursor,self.shape,self.sequence,self.history,self.snapshot=advance((self.strengths,self.folded,self.cursor,self.shape,self.sequence,self.history,self.snapshot),a)
  elif a==6:
   if (self.strengths,self.folded,self.cursor,self.shape,self.sequence,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

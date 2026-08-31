"""a125 Nested Neighborhood -- mark nodes defined by neighbors of neighbors."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MAP,ROOM_A,ROOM_B,DOOR,MARK,CURSOR,VALID,INVALID,BAD=6,8,12,14,9,10,13,4,11,15
ADJ=((1,7),(0,2,4),(1,3),(2,4),(1,3,5),(4,6),(5,7),(6,0))
LEVELS=[
 {"name":"Mark Room","seq":(1,)},{"name":"Select Room","seq":(2,)},
 {"name":"Change Kind","seq":(3,1)},{"name":"Inspect Neighbors","seq":(1,2,3,4,2)},
 {"name":"Inspect Neighbors Twice","seq":(1,3,2,1,4,3,2)},{"name":"Nested Neighborhood","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 marks,cursor,kind,valid,invalid,history,snapshot=s;m=list(marks)
 if a==1:m[cursor]=(m[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:kind=(kind+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  valid=0
  for i in range(8):valid+=int(all(any(m[k]==(kind+1)%3 for k in ADJ[j]) for j in ADJ[i]))
  invalid=8-valid;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(m),cursor,kind,valid,invalid,history)
 return tuple(m),cursor,kind,valid,invalid,history,snapshot
for q in LEVELS:
 s=((0,1,2,0,1,2,0,1),0,0,0,8,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MAP;pts=((31,8),(47,15),(55,31),(47,47),(31,55),(15,47),(7,31),(15,15));cols=(ROOM_A,ROOM_B,MARK)
  for i,neighbors in enumerate(ADJ):
   x,y=pts[i]
   for j in neighbors:
    if j>i:
     xx,yy=pts[j];f[min(y,yy):max(y+1,yy+1),min(x,xx):max(x+1,xx+1)]=DOOR
  for i,(x,y) in enumerate(pts):
   f[y-5:y+6,x-5:x+6]=cols[g.marks[i]]
   if i==g.cursor:f[y-8:y-6,x-6:x+7]=CURSOR
  f[54:58,8:8+g.valid*5]=VALID;f[7:10,8:8+g.invalid*5]=INVALID
  if g.bad:f[1:4,18:46]=BAD
  return f
class A125(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a125",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.marks,self.cursor,self.kind,self.valid,self.invalid,self.history,self.snapshot=((0,1,2,0,1,2,0,1),0,0,0,8,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.marks,self.cursor,self.kind,self.valid,self.invalid,self.history,self.snapshot=advance((self.marks,self.cursor,self.kind,self.valid,self.invalid,self.history,self.snapshot),a)
  elif a==6:
   if (self.marks,self.cursor,self.kind,self.valid,self.invalid,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""a115 Rotating Assignment -- anticipate compatibility changes with limited recourse."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,ORBIT,WORKER,STATION,EDGE,PHASE,RECOURSE,INCOMPATIBLE,LOCKED,BAD=12,8,9,14,10,13,11,6,4,15
LEVELS=[
 {"name":"Reassign","seq":(1,)},{"name":"Select Worker","seq":(2,)},
 {"name":"Advance Phase","seq":(3,1)},{"name":"Check Compatibility","seq":(1,2,3,4,2)},
 {"name":"Budget Recourse","seq":(1,3,2,1,4,3,2)},{"name":"Rotating Assignment","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 assignments,cursor,phase,moves,incompatible,locked,history,snapshot=s;ass=list(assignments)
 if a==1:ass[cursor]=(ass[cursor]+1)%5;moves=(moves+1)%6;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:phase=(phase+1)%4;moves=0;history=(history+(3,))[-8:]
 elif a==4:incompatible=sum(int(ass[i] not in ((i+phase)%5,(i+phase+1)%5)) for i in range(5));locked=sum(int(ass[i]==(i+phase)%5) for i in range(5));history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(ass),cursor,phase,moves,incompatible,locked,history)
 return tuple(ass),cursor,phase,moves,incompatible,locked,history,snapshot
for x in LEVELS:
 s=((0,1,2,3,4),0,0,0,0,5,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORBIT
  stations=((31,8),(49,22),(43,47),(19,47),(13,22))
  workers=((31,21),(40,28),(37,40),(25,40),(22,28))
  for i,(x,y) in enumerate(stations):f[y-4:y+5,x-4:x+5]=STATION
  for i,(x,y) in enumerate(workers):
   f[y-3:y+4,x-3:x+4]=WORKER;tx,ty=stations[g.assignments[i]];f[min(y,ty):max(y+1,ty+1),min(x,tx):max(x+1,tx+1)]=EDGE
   if i==g.cursor:f[y-6:y-4,x-5:x+6]=PHASE
  f[54:58,8:8+g.moves*8]=RECOURSE;f[7:10,8:8+g.incompatible*8]=INCOMPATIBLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A115(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a115",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.assignments,self.cursor,self.phase,self.moves,self.incompatible,self.locked,self.history,self.snapshot=((0,1,2,3,4),0,0,0,0,5,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.assignments,self.cursor,self.phase,self.moves,self.incompatible,self.locked,self.history,self.snapshot=advance((self.assignments,self.cursor,self.phase,self.moves,self.incompatible,self.locked,self.history,self.snapshot),a)
  elif a==6:
   if (self.assignments,self.cursor,self.phase,self.moves,self.incompatible,self.locked,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

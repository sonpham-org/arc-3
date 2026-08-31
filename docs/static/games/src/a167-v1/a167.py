"""a167 Symmetry Pruning -- mark one unexplored branch per rotational class."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,ROOM,BRANCH,REPRESENTATIVE,ROTATION,CURSOR,CLASS,UNMARKED,DUPLICATE,SEARCH=3,8,7,12,10,13,4,11,6,9
BAD=15
CLASSES=(0,1,2,0,1,2,0,1)
LEVELS=[
 {"name":"Mark Branch","seq":(1,)},{"name":"Select Branch","seq":(2,)},
 {"name":"Rotate Room","seq":(3,1)},{"name":"Find Classes","seq":(1,2,3,4,2)},
 {"name":"Prune Copies","seq":(1,3,2,1,4,3,2)},{"name":"Symmetry Pruning","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 marked,cursor,rotation,classes,unmarked,duplicates,history,snapshot=s
 if a==1:marked^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:rotation=(rotation+1)%4;history=(history+(3,))[-8:]
 elif a==4:
  counts=[sum(int((marked>>i)&1) for i,c in enumerate(CLASSES) if c==k) for k in range(3)];classes=sum(int(x>0) for x in counts);unmarked=sum(int(x==0) for x in counts);duplicates=sum(max(0,x-1) for x in counts);history=(history+(4,))[-8:]
 elif a==5:snapshot=(marked,cursor,rotation,classes,unmarked,duplicates,history)
 return marked,cursor,rotation,classes,unmarked,duplicates,history,snapshot
for q in LEVELS:
 s=(0b00000111,0,0,3,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ROOM;pts=((31,8),(47,15),(55,31),(47,47),(31,55),(15,47),(7,31),(15,15))
  for i,(x,y) in enumerate(pts):
   f[y-5:y+6,x-5:x+6]=REPRESENTATIVE if (g.marked>>i)&1 else BRANCH;f[y-2:y+3,x-2:x+3]=CLASS
   if i==g.cursor:f[y-8:y-6,x-6:x+7]=CURSOR
  f[54:58,8:8+g.classes*12]=SEARCH;f[7:10,8:8+g.unmarked*10]=UNMARKED;f[7:10,43:43+g.duplicates*4]=DUPLICATE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A167(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a167",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.marked,self.cursor,self.rotation,self.classes,self.unmarked,self.duplicates,self.history,self.snapshot=(0b00000111,0,0,3,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.marked,self.cursor,self.rotation,self.classes,self.unmarked,self.duplicates,self.history,self.snapshot=advance((self.marked,self.cursor,self.rotation,self.classes,self.unmarked,self.duplicates,self.history,self.snapshot),a)
  elif a==6:
   if (self.marked,self.cursor,self.rotation,self.classes,self.unmarked,self.duplicates,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

import os
import json
import argparse
import pandas as pd
import myutils

    
def get_i_ni(defect):
    
    if defect["type"][0] == "v": 
        ## for vacancies, an atom of species "species" is removed
        species = [defect["species"]]
        ni = [-1]
        
    if defect["type"][0] == "a" or defect["type"][0] == "i":
        ## for adatoms or intersititals, an atom of species "species_new" is added
        species = [defect["species_new"]]
        ni = [1]
        
    if defect["type"][0] == "s":
        ## for substitutions, an atom of species "species" is removed 
        ## and an atom of "species_new" is added
        species = [defect["species"],defect["species_new"]]
        ni = [-1,1]
    
    return (species, ni)


def main(args):
    
    ## define a main function callable from another python script
        
    parser = argparse.ArgumentParser(description='Evaluate uncorrected defect formation energy.')
    parser.add_argument('main_system',help='the main system e.g. MoS2, WSe2')
    parser.add_argument('dir_db',help='path to the database directory')
    parser.add_argument('dir_def',help='path to the defect directory containing the \
                                        excel, initdefect.json files')
    parser.add_argument('xlfile',help='excel filename to read/save the dataframe to')
    parser.add_argument('mu_limit',help='which chemical potential limit to consider, \
                                         e.g. Mo-rich')
    parser.add_argument('--functional',help='functional that was used for this set \
                                             of calculations', default='GGA')
    parser.add_argument('--soc',help='whether or not to look in soc(dos) subdirectory',
                        default=False,action='store_true')
    parser.add_argument('--logfile',help='logfile to save output to')
       
    ## read in the above arguments from command line
    args = parser.parse_args(args)
    
    ## set up logging
    if args.logfile:
        myLogger = myutils.setup_logging(args.logfile)
    else:
        myLogger = myutils.setup_logging()


    ## load list of dataframes from sheets from excel file    
    df = pd.read_excel(os.path.join(args.dir_def,args.xlfile),sheet_name=None)
    
 
    ## find initdef.json file
    if myutils.check_file_exists(args.dir_def,"initdef") == True:
        for file in os.listdir(args.dir_def): 
            if file.startswith("initdef"):
                file_initdef = file
        ##  get species i and ni from initdefect.json file           
        with open(os.path.join(args.dir_def,file_initdef), 'r') as file:
            initdef = json.loads(file.read())
            species_list, ni_list = [],[]
            for defect in initdef:
                species, ni = get_i_ni(initdef[defect])
                species_list += species
                ni_list += ni
        myLogger.info("Atoms added/removed: " + \
                     ", ".join([str(n)+"*"+i for n,i in zip(ni_list,species_list)]))

   
    for q in [qi for qi in df.keys()]:
        
        ## get the relevant chemical potentials
        found_mu = True
        for species in species_list:
            mu = "mu_%s_%s"%(species,args.mu_limit)
            
            ## check if the relevant database entry exists
            if myutils.check_file_exists(args.dir_db,"%s.json"%species) == True:
                dbentry_file = "%s.json"%species
                with open(os.path.join(args.dir_db, dbentry_file), 'r') as file:
                    mater = json.loads(file.read())
                ## search for appropriate mu entry
                mu_key = "mu"
                for key in mater[args.functional].keys():
                    if key.startswith("mu_%s"%args.mu_limit):
                        mu_key = key
                myLogger.info("Using chemical potential " + mu_key + " from " + dbentry_file)                    
                ## input the corresponding mus into the dataframe
                df[q][mu] = mater[args.functional][mu_key]
                
            else:
                myLogger.info("Cannot find the database entry for " + species)
                found_mu = False
    
    
        ## get the VBMs
        ## check if the relevant database entry exists
        if myutils.check_file_exists(args.dir_db,"%s.json"%args.main_system) == True:
            dbentry_file = "%s.json"%(args.main_system)
            with open(os.path.join(args.dir_db, dbentry_file), 'r') as file:
                mater = json.loads(file.read())   
                
            ## input the VBMs corresponding to each vacuum spacing into the dataframe
            for rowind in df[q].index.values:
                vac = df[q].loc[rowind].vacuum
                if vac in mater[args.functional].keys():
                    df[q].at[rowind,'VBM'] = mater[args.functional][vac]["VBM"]
                else:
                    myLogger.info("Cannot find the VBM entry for " + vac) 
                  
            ## Finally, we can compute the uncorrected defect formation energy:
            ## Eform = Etot(def) - Etot(pristine) - sum(n_i*mu_i) + q*E_Fermi
            if found_mu:
                ## proceed if chemical potentials and VBMs have been correctly entered
                sum_mu = 0
                for n,species in zip(ni_list,species_list):
                    mu = "mu_%s_%s"%(species,args.mu_limit)
                    sum_mu += n * df[q][mu]
                if q == 'charge_0': 
                    colname = "E_form_corr"
                else:
                    colname = "E_form_uncorr"
                df[q][colname] = df[q].loc[:,'E_def'] \
                                 - df[q].loc[:,'E_bulk'] \
                                 - sum_mu \
                                 + int(q.split("_")[-1]) * df[q].loc[:,'VBM']                                  
         
        else:
            myLogger.info("Cannot find the database entry for " + args.main_system)


    ## write the updated excel file
    writer = pd.ExcelWriter(myutils.joinpath(args.dir_def,args.xlfile))
    for q in df.keys():  
        df[q].to_excel(writer, q, index=False)
    writer.save() 
    
    
if __name__ == '__main__':

    
    main(sys.argv[1:])
    
    